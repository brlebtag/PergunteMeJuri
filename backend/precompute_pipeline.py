# Script para montar a pipeline pre-computada do sistema de Hybrid Search (H-RAG)
# https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
import os
# import asyncio
import re
import hashlib
import unicodedata
from typing import TypedDict, Annotated, Any, Optional, List
import semchunk
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine, text, Connection
from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader
from pathlib import Path

from backend.config import (
    CACHE_DIR,
    CHUNK_SIZE,
    DOC_FOLDER,
    EMBEDDING_MODEL,
    OVERLAP,
    PREFIX_PASSAGE,
    SQL_ECHO,
    URL_BANCO,
)

def docs_folder() -> Path:
    return Path(DOC_FOLDER)

def doc_file(name: str) -> str:
    return os.path.join(DOC_FOLDER, name)

def docs_files() -> List[(str, str)]:
    return [(f.name, doc_file(f.name)) for f in docs_folder().rglob("*.pdf") if f.is_file()]

# Categorias Unicode descartadas do texto extraido do PDF:
#   Co = uso privado. Extratores mapeiam glifos de fontes embutidas para essas
#        faixas (ex.: U+F24E), gerando lixo que nao representa texto nenhum.
#   Cc = caracteres de controle (menos \n e \t, preservados abaixo).
CATEGORIAS_LIXO = ("Co", "Cc")
ESPACOS_RE = re.compile(r"[^\S\n]+")

def limpar_texto(texto: str) -> str:
    """Remove lixo de extracao de PDF antes do chunking."""
    texto = unicodedata.normalize("NFKC", texto)
    texto = "".join(
        c for c in texto
        if c in "\n\t" or unicodedata.category(c) not in CATEGORIAS_LIXO
    )
    # Colapsa sequencias de espacos sem juntar linhas.
    return ESPACOS_RE.sub(" ", texto).strip()

def build_tokenizer():
    return AutoTokenizer.from_pretrained(EMBEDDING_MODEL, cache_dir=CACHE_DIR)

def build_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL, cache_folder=CACHE_DIR)

def build_chunker(tokenizer, chunk_size = CHUNK_SIZE):
    return semchunk.chunkerify(tokenizer, chunk_size)

def search_doc(conn: Connection, absolute_path: str) -> int:
    sql = text("""SELECT id FROM documents WHERE absolute_path = :absolute_path;""")
    data = {"absolute_path": absolute_path}
    ret = conn.execute(sql, data)
    row = ret.fetchone()
    return row[0] if row else None

def insert_doc(conn: Connection, name: str, absolute_path: str) -> int:
    try:
        sql = text("""INSERT INTO documents ("name", absolute_path)
            VALUES (:name, :absolute_path) RETURNING id;""")
        data = {"name": name, "absolute_path": absolute_path}
        ret = conn.execute(sql, data)
        row = ret.fetchone()
        conn.commit()
        return row[0]
    except IntegrityError:
        conn.rollback()
        return search_doc(conn, absolute_path)

def to_vector_literal(embedding) -> str:
    """pgvector espera o formato textual '[0.1,0.2,...]'."""
    return "[" + ",".join(repr(float(v)) for v in embedding) + "]"

def insert_chunk(conn: Connection, doc_id: int, content: str, embedding, hash_: str) -> Optional[int]:
    try:
        sql = text("""INSERT INTO document_chunks (document_id, content, embedding, hash)
            VALUES (:document_id, :content, CAST(:embedding AS vector), :hash)
            RETURNING id;""")
        data = {"document_id": doc_id,
                "content": content,
                "embedding": to_vector_literal(embedding),
                "hash": hash_}
        ret = conn.execute(sql, data)
        row = ret.fetchone()
        conn.commit()
        return row[0]
    except IntegrityError:
        conn.rollback()
        return None

def store_chunk(conn: Connection, model: SentenceTransformer, doc_id: int, chunk: str) -> Optional[int]:
    hash_ = hashlib.sha256(chunk.encode('utf-8')).hexdigest()
    embedding = model.encode(PREFIX_PASSAGE + chunk, normalize_embeddings=True)
    return insert_chunk(conn, doc_id, chunk, embedding, hash_)

def precompute():
    tokenizer = build_tokenizer()
    chunker = build_chunker(tokenizer)
    engine = create_engine(URL_BANCO, echo=SQL_ECHO)
    model = build_embedding_model()
    with engine.connect() as conn:
        for (name, filename) in docs_files():
            reader = PdfReader(filename)
            doc_id = insert_doc(conn, name.replace(".pdf", ""), filename)
            if doc_id is None:
                continue
            for page in reader.pages:
                texto = limpar_texto(page.extract_text() or "")
                if not texto.strip():
                    continue
                for chunk in chunker(texto):
                    if chunk.strip():
                        store_chunk(conn, model, doc_id, chunk)


def main() -> None:
    precompute()

if __name__ == "__main__":
    main()