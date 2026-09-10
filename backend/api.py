# API HTTP que expoe o Juri para o frontend.
import json
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.config import API_HOST, API_PORT, CORS_ORIGINS
from backend.juri import abrir_juri, client, executar


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Abre as dependencias uma vez na subida e fecha no encerramento.

    O grafo carrega a tool MCP e mantem a conexao do checkpointer, entao
    precisa viver enquanto o servidor viver -- nao por requisicao.
    """
    async with abrir_juri() as graph:
        app.state.graph = graph
        yield


app = FastAPI(
    title="PergunteMeJuri",
    description="Chatbot juridico com RAG hibrido sobre leis brasileiras.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1, description="Pergunta em linguagem natural.")
    thread_id: str | None = Field(
        default=None,
        description="Identifica a conversa. Omitido, uma nova e criada.",
    )


def _evento(nome: str, **dados) -> dict:
    return {"event": nome, "data": json.dumps(dados, ensure_ascii=False)}


@app.post("/perguntar")
async def perguntar(corpo: Pergunta):
    """Responde em streaming (SSE), token a token.

    Eventos emitidos:
      inicio -> {"thread_id"}  antes de qualquer token, para o cliente guardar
                               a conversa criada
      token  -> {"texto"}      pedacos da resposta, na ordem
      fim    -> {"thread_id"}  conclusao normal
      erro   -> {"detalhe"}    falha no meio do stream
    """
    graph = app.state.graph
    thread_id = corpo.thread_id or str(uuid.uuid4())
    thread = {"configurable": {"thread_id": thread_id}}
    entrada = {"messages": [HumanMessage(content=corpo.pergunta)]}

    async def eventos():
        yield _evento("inicio", thread_id=thread_id)
        try:
            async for chunk, metadata in graph.astream(
                entrada, thread, stream_mode="messages"
            ):
                # O no de reescrita tambem chama o LLM; so os tokens da
                # resposta final interessam ao cliente.
                if metadata.get("langgraph_node") == "generate" and chunk.content:
                    yield _evento("token", texto=chunk.content)
        except Exception as e:
            # O status HTTP ja foi enviado com o primeiro evento: a falha
            # precisa chegar pelo proprio stream.
            yield _evento("erro", detalhe=str(e))
            return
        yield _evento("fim", thread_id=thread_id)

    return EventSourceResponse(eventos())


@app.get("/conversas/{thread_id}")
async def conversa(thread_id: str):
    """Historico de uma conversa, para o frontend reabrir onde parou."""
    estado = await app.state.graph.aget_state({"configurable": {"thread_id": thread_id}})
    if not estado.values:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada.")

    return {
        "thread_id": thread_id,
        "mensagens": [
            {
                "autor": "juri" if isinstance(m, AIMessage) else "usuario",
                "texto": m.content,
            }
            for m in estado.values.get("messages", [])
        ],
    }


@app.get("/leis")
async def leis():
    """Nomes das leis indexadas.

    Vem do resource do servidor MCP, e nao de uma consulta direta ao banco:
    assim a API nao precisa importar o hrag, que carregaria o modelo de
    embedding (~500MB) neste processo sem necessidade.
    """
    recursos = await client.get_resources("rag", uris="file://laws")
    nomes = []
    for recurso in recursos:
        try:
            nomes.extend(json.loads(recurso.as_string()))
        except (json.JSONDecodeError, AttributeError):
            continue
    return {"leis": nomes}


@app.get("/saude")
async def saude():
    return {"status": "ok"}


def main() -> None:
    # loop="none": quem cria o event loop e o executar(), que no Windows usa o
    # SelectorEventLoop exigido pelo psycopg async. Deixar o uvicorn escolher
    # traria de volta o ProactorEventLoop e quebraria o checkpointer.
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, loop="none")
    executar(uvicorn.Server(config).serve())


if __name__ == "__main__":
    main()
