# Realiza Hybrid searh para encontrar documentos/trechos relevantes para serem providos como contexto para Juri.
import os
import uuid
from typing import TypedDict, Annotated, Any, Optional, List, cast
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sentence_transformers import SentenceTransformer

MODEL = "intfloat/multilingual-e5-small"
PREFIX_PASSAGE = "passage: "
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelos_cache")
URL_BANCO = "postgresql+psycopg2://postgres:root@localhost:5432/pergunteme_juri"
LIMIT = 10

engine = create_engine(URL_BANCO, echo=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
mcp = FastMCP("HybridRAG")
model = SentenceTransformer(MODEL, cache_folder=CACHE_DIR)

class DocumentChunk(TypedDict):
    id: int
    content: str
    document_id: int
    score: float

def to_vector_literal(embedding) -> str:
    """pgvector espera o formato textual '[0.1,0.2,...]'."""
    return "[" + ",".join(repr(float(v)) for v in embedding) + "]"

def reciprocal_rank_fusion(results_list: list[list[DocumentChunk]], k: int = 60) -> list[DocumentChunk]:
    rrf_scores: dict[uuid.UUID, float] = {}
    results_by_id: dict[uuid.UUID, DocumentChunk] = {}
    for result_list in results_list:
        for rank, result in enumerate(result_list, start=1):
            rrf_scores[result.id] = rrf_scores.get(
                result.id, 0.0
            ) + 1.0 / (k + rank)
            results_by_id[result.id] = result

    sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)

    return [
        DocumentChunk(
            id = chunk_id,
            content=results_by_id[chunk_id].content,
            document_id=results_by_id[chunk_id].document_id,
            score=rrf_scores[chunk_id],
        )
        for chunk_id in sorted_ids
    ]

def semantic_search(session: Session, search: str) -> List[DocumentChunk]:
    try:
        embedding = model.encode(PREFIX_PASSAGE + search, normalize_embeddings=True)
        sql = text("""
    SELECT 
        document_chunks.id, 
        document_chunks.content, 
        document_chunks.document_id, 
        (1 - (document_chunks.embedding <=> :embedding)) AS score
    FROM document_chunks 
    ORDER BY document_chunks.embedding <=> :embedding ASC
    LIMIT :limit;
    """)
        data = {"embedding": to_vector_literal(embedding), "limit": LIMIT}
        ret = session.execute(sql, data)
        docs_chunks: list[DocumentChunk] = [
            cast(DocumentChunk, dict(row)) for row in ret.mappings().all()
        ]
        return docs_chunks
    except Exception as e:
        print(e)
    return []

def keyword_search(session: Session, search: str) -> list[DocumentChunk]:
    try:
        sql = text("""
    SELECT 
        document_chunks.id, 
        document_chunks.content, 
        document_chunks.document_id, 
        ts_rank(document_chunks.search_vector, plainto_tsquery('english', :search)) AS score
    FROM document_chunks 
    WHERE document_chunk.search_vector @@ plainto_tsquery('portuguese', :search)
    ORDER BY relevance DESC
    LIMIT :limit;
    """)
        data = {"search": search, "limit": LIMIT}
        ret = session.execute(sql, data)
        docs_chunks: list[DocumentChunk] = [
            cast(DocumentChunk, dict(row)) for row in ret.mappings().all()
        ]
        return docs_chunks
    except Exception as e:
        print(e)
    return []

def hybrid_search(session: Session, search: str) -> list[DocumentChunk]:
    list1 = semantic_search(session, search)
    list2 = semantic_search(session, search)
    final_list = reciprocal_rank_fusion([list1, list2])
    return final_list[:LIMIT]

@mcp.tool()
def get_laws(search: str) -> List[DocumentChunk]:
    f"""Search most {LIMIT}th relevant documents based on 'search' term."""
    try:
        with SessionLocal as session:
            docs_chunks = hybrid_search(session, search)
            return docs_chunks
    except Exception as e:
        print(e)
    return []

if __name__ == "__main__":
    mcp.run(transport="http", host="localhost", port=8000)