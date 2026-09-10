# Cria banco de dados
import os
from sqlalchemy import create_engine, text

from backend.config import SQL_ECHO, URL_BANCO

LANG="portuguese"

BUILD_TABLES = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
	id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
	source_path TEXT NOT NULL UNIQUE,
	metadata JSONB DEFAULT '{}',
	created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_chunks (
	id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id int NOT NULL REFERENCES documents(id),
    content TEXT NOT NULL,
    embedding vector(384),
    hash CHAR(64) NOT NULL UNIQUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector(:lang, content)) STORED;

CREATE INDEX IF NOT EXISTS idx_chunks_search ON document_chunks USING gin(search_vector);
"""

def main() -> None:
    engine = create_engine(URL_BANCO, echo=SQL_ECHO)
    with engine.connect() as conn:
        conn.execute(text(BUILD_TABLES), {"lang": LANG})
        conn.commit()


if __name__ == "__main__":
    main()