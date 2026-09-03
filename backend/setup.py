# Cria banco de dados
from sqlalchemy import create_engine, text

URL_BANCO = "postgresql+psycopg2://postgres:root@localhost:5432/pergunteme_juri"

BUILD_TABLES = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
	id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	absolute_path TEXT NOT NULL UNIQUE,
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

CREATE INDEX idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

ALTER TABLE document_chunks
    ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('portuguese', content)) STORED;

CREATE INDEX idx_chunks_search ON document_chunks USING gin(search_vector);
"""

def main() -> None:
    engine = create_engine(URL_BANCO, echo=True)
    with engine.connect() as conn:
        conn.execute(text(BUILD_TABLES))
        conn.commit()


if __name__ == "__main__":
    main()