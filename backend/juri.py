# Chatbot responsavel por responder perguntas relacionadas as leis brasileiras
import asyncio
import json
from contextlib import asynccontextmanager

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, RemoveMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_mcp_adapters.client import MultiServerMCPClient

from backend.config import (
    CHECKPOINT_URL,
    LLM_NUM_CTX,
    LLM_REASONING,
    LLM_TEMPERATURE,
    MCP_URL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

llm = ChatOllama(model=OLLAMA_MODEL,
    temperature=LLM_TEMPERATURE,
    num_ctx=LLM_NUM_CTX,
    reasoning=LLM_REASONING,
    base_url=OLLAMA_BASE_URL)

client = MultiServerMCPClient({
    "rag": {
        "transport": "streamable_http",       # ou "stdio"
        "url": MCP_URL,
    }
})

TOOL_NAME = "search_laws"

PROMPT_SISTEMA = """Você é um agente de IA jurídico.
Responda perguntas somente que estão relacionadas as leis e usando apenas o contexto legal fornecido.
Se não for possível responder com base no contexto legal fornecido, informe que não é possível responder a pergunta.
Abaixo segue o contexto legal e a pergunta feita:

{contexto}
"""

rag_tool = None


class EstadoJuri(MessagesState):
    """Estado do grafo.

    O contexto legal fica fora de `messages` de proposito: com checkpointer,
    tudo que entra em `messages` e persistido e reenviado a cada turno, e os
    ~3k tokens de leis de cada pergunta estourariam a janela em poucas trocas.
    Aqui ele e sobrescrito a cada `retrieve`.
    """
    contexto: str


async def carregar_rag_tool():
    global rag_tool
    tools = await client.get_tools()
    rag_tool = next((t for t in tools if t.name == TOOL_NAME), None)
    if rag_tool is None:
        raise RuntimeError(
            f"Ferramenta '{TOOL_NAME}' nao encontrada no servidor MCP. "
            f"Ferramentas disponiveis: {[t.name for t in tools]}"
        )


def extrair_chunks(result) -> list[dict]:
    """Normaliza a resposta da tool MCP para uma lista de chunks.

    O adaptador devolve blocos de conteudo no formato
    [{"type": "text", "text": "<json>"}], e nao os objetos ja desserializados.
    """
    if isinstance(result, list) and result and isinstance(result[0], dict) and "text" in result[0]:
        result = "".join(bloco.get("text", "") for bloco in result)
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return [{"document_name": "", "content": result}]
    if isinstance(result, dict):
        result = result.get("result", [])
    return [chunk for chunk in result if isinstance(chunk, dict)]


async def retrieve_node(state: EstadoJuri):
    question = state["messages"][-1].content
    result = await rag_tool.ainvoke({"query": question})
    chunks = extrair_chunks(result)
    if not chunks:
        contexto = "Nenhum trecho de lei relevante foi encontrado."
    else:
        contexto = "\n\n".join(
            f"[{c.get('document_name', '')}] {c.get('content', '')}" for c in chunks
        )
    return {"contexto": contexto}


async def generate_node(state: EstadoJuri):
    instrucoes = PROMPT_SISTEMA.format(contexto=state.get("contexto", ""))
    messages = [SystemMessage(content=instrucoes)] + state["messages"]
    response = await llm.ainvoke(messages)
    return {"messages": response}


def construir_workflow() -> StateGraph:
    workflow = StateGraph(EstadoJuri)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)

    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    return workflow


@asynccontextmanager
async def abrir_juri():
    """Sobe as dependencias externas e entrega o grafo pronto para uso.

    O checkpointer mantem o historico por thread_id no Postgres, entao a
    conversa sobrevive ao fim do processo. E um context manager porque a
    conexao precisa ser fechada no encerramento -- e o formato que o lifespan
    do FastAPI espera.
    """
    await carregar_rag_tool()
    async with AsyncPostgresSaver.from_conn_string(CHECKPOINT_URL) as checkpointer:
        # Cria as tabelas do checkpointer na primeira execucao; idempotente.
        await checkpointer.setup()
        yield construir_workflow().compile(checkpointer=checkpointer)


async def responder(graph, pergunta: str, thread_id: str):
    """Envia uma pergunta e imprime a resposta token a token."""
    thread = {"configurable": {"thread_id": thread_id}}
    entrada = {"messages": [HumanMessage(content=pergunta)]}

    print(f"\n> {pergunta}\n")
    # Em stream_mode="messages" cada evento e uma tupla (chunk, metadata) com os
    # tokens do LLM saindo aos poucos, em vez do estado completo do grafo.
    async for chunk, metadata in graph.astream(entrada, thread, stream_mode="messages"):
        if metadata.get("langgraph_node") == "generate" and chunk.content:
            print(chunk.content, end="", flush=True)
    print()


async def main():
    async with abrir_juri() as graph:
        # As duas perguntas compartilham o thread_id: a segunda so faz sentido
        # se o historico da primeira tiver sido recuperado do Postgres.
        await responder(graph, "Quem é considerado cidadão brasileiro?", "1")
        await responder(graph, "E em quais casos essa nacionalidade é perdida?", "1")


if __name__ == "__main__":
    asyncio.run(main())
