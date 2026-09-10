# Realiza Hybrid searh para encontrar documentos/trechos relevantes para serem providos como contexto para Juri.
import os
import uuid
from typing import TypedDict, Annotated, Any, Optional, List, cast
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, Field

from backend.config import (
    CACHE_DIR,
    EMBEDDING_MODEL,
    LIMIT,
    MCP_HOST,
    MCP_PORT,
    PREFIX_QUERY,
    SQL_ECHO,
    URL_BANCO,
)

engine = create_engine(URL_BANCO, echo=SQL_ECHO)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
mcp = FastMCP("HybridRAG")
model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=CACHE_DIR)

class DocumentChunk(BaseModel):
    """A Chunk of information extracted from a document"""
    id: int = Field(description="Document Chunk id")
    content: str = Field(description="Document Chunk's Content")
    document_id: int = Field(description="Document Id")
    document_name: str = Field(description="Document Name")
    score: float = Field(description="Document Chunk relevance score. Higher the value, higher the confidence this particular document chunk is relevant to the query.")

def to_vector_literal(embedding) -> str:
    """pgvector espera o formato textual '[0.1,0.2,...]'."""
    return "[" + ",".join(repr(float(v)) for v in embedding) + "]"

def reciprocal_rank_fusion(results_list: list[list[DocumentChunk]], k: int = 60) -> list[DocumentChunk]:
    rrf_scores: dict[int, float] = {}
    results_by_id: dict[int, DocumentChunk] = {}
    for result_list in results_list:
        for rank, result in enumerate(result_list, start=1):
            rrf_scores[result.id] = rrf_scores.get(
                result.id, 0.0
            ) + 1.0 / (k + rank)
            results_by_id[result.id] = result

    sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)

    return [
        DocumentChunk(
            id=chunk_id,
            content=results_by_id[chunk_id].content,
            document_id=results_by_id[chunk_id].document_id,
            document_name=results_by_id[chunk_id].document_name,
            score=rrf_scores[chunk_id],
        )
        for chunk_id in sorted_ids
    ]

def semantic_search(session: Session, query: str) -> list[DocumentChunk]:
    try:
        embedding = model.encode(PREFIX_QUERY + query, normalize_embeddings=True)
        sql = text("""
    SELECT 
        document_chunks.id, 
        document_chunks.content, 
        document_chunks.document_id, 
        (1 - (document_chunks.embedding <=> :embedding)) AS score,
        documents."name" AS document_name
    FROM document_chunks
    INNER JOIN documents ON documents.id = document_chunks.document_id
    ORDER BY document_chunks.embedding <=> :embedding ASC
    LIMIT :limit;
    """)
        data = {"embedding": to_vector_literal(embedding), "limit": LIMIT}
        ret = session.execute(sql, data)
        docs_chunks: list[DocumentChunk] = [
            DocumentChunk(**row) for row in ret.mappings().all()
        ]
        return docs_chunks
    except Exception as e:
        print(e)
    return []

def keyword_search(session: Session, query: str) -> list[DocumentChunk]:
    try:
        # plainto_tsquery une os termos com AND, o que zera o resultado para
        # perguntas em linguagem natural. Trocamos por OR e deixamos o ts_rank
        # ordenar: quem casa mais termos sobe.
        sql = text("""
    WITH q AS (
        SELECT replace(plainto_tsquery('portuguese', :query)::text, ' & ', ' | ')::tsquery AS tsq
    )
    SELECT 
        document_chunks.id, 
        document_chunks.content, 
        document_chunks.document_id, 
        ts_rank(document_chunks.search_vector, q.tsq) AS score,
        documents."name" AS document_name
    FROM document_chunks
    INNER JOIN documents ON documents.id = document_chunks.document_id 
    CROSS JOIN q
    WHERE document_chunks.search_vector @@ q.tsq
    ORDER BY score DESC
    LIMIT :limit;
    """)
        data = {"query": query, "limit": LIMIT}
        ret = session.execute(sql, data)
        docs_chunks: list[DocumentChunk] = [
            DocumentChunk(**row) for row in ret.mappings().all()
        ]
        return docs_chunks
    except Exception as e:
        print(e)
    return []

def get_all_docs_names(session: Session) -> list[str]:
    try:
        sql = text("""
        SELECT 
            "name"
        FROM documents
        """)
        ret = session.execute(sql)
        data = []
        for row in ret:
            data.append(row[0])
        return data
    except Exception as e:
        print(e)
    return []

def hybrid_search(session: Session, query: str) -> list[DocumentChunk]:
    list1 = keyword_search(session, query)
    list2 = semantic_search(session, query)
    final_list = reciprocal_rank_fusion([list1, list2])
    return final_list[:LIMIT]

@mcp.tool(
    description=f"""Search the most relevant chunks of documents based on 'search' up to {LIMIT} chunks.
        Parameters: A query to be searched using hybrid search (key-based and semantic search).
        Returns: A list of chunks of laws ordered by relevance to the query.
                Each chunk has: id, content, document_id and score.
    """
)
def search_laws(query: str) -> list[DocumentChunk]:
    """Search the most relevant chunks of documents based on 'search'.
        Parameters: A query to be searched using hybrid search (key-based and semantic search).
        Returns: A list of chunks of laws ordered by relevance to the query.
                Each chunk has: id, content, document_id and score.
    """
    try:
        with SessionLocal() as session:
            docs_chunks = hybrid_search(session, query)
            return docs_chunks
    except Exception as e:
        print(e)
    return []

@mcp.resource("file://laws")
def list_laws() -> list[str]:
    """List all avaliable laws that you can query.
        Returns: A list of names of laws.
    """
    try:
        with SessionLocal() as session:
            return get_all_docs_names(session)
    except Exception as e:
        print(e)
    return []

if __name__ == "__main__":
    mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)