# Chatbot responsavel por responder perguntas relacionadas as leis brasileiras
import asyncio
import json
import pprint
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, RemoveMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient

from backend.config import (
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

rag_tool = None


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


async def retrieve_node(state: MessagesState):
    question = state["messages"][-1].content
    result = await rag_tool.ainvoke({"query": question})
    chunks = extrair_chunks(result)
    if not chunks:
        contexto = "Nenhum trecho de lei relevante foi encontrado."
    else:
        contexto = "\n\n".join(
            f"[{c.get('document_name', '')}] {c.get('content', '')}" for c in chunks
        )
    return {"messages": [SystemMessage(content=f"Contexto legal:\n{contexto}")]}

async def generate_node(state: MessagesState):
    messages = [SystemMessage(content=f"""Você é um agente de IA jurídico.
    Responda perguntas somente que estão relacionadas as leis e usando apenas o contexto legal fornecido.
    Se não for possível responder com base no contexto legal fornecido, informe que não é possível responder a pergunta.
    Abaixo segue o contexto legal e a pergunta feita:\n\n""")] + state["messages"]
    response = await llm.ainvoke(messages)
    return {"messages": response}

workflow = StateGraph(MessagesState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)

graph = workflow.compile()

async def main():
    await carregar_rag_tool()

    # Input
    initial_input = {"messages": HumanMessage(content="Quem é considerado cidadão brasileiro?")}

    # Thread
    thread = {"configurable": {"thread_id": "1"}}

    # Os nos sao async, entao o grafo precisa ser executado pela API assincrona.
    # Em stream_mode="messages" cada evento e uma tupla (chunk, metadata) com os
    # tokens do LLM saindo aos poucos, em vez do estado completo do grafo.
    async for chunk, metadata in graph.astream(initial_input, thread, stream_mode="messages"):
        if metadata.get("langgraph_node") == "generate" and chunk.content:
            print(chunk.content, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())