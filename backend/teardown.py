# Cria banco de dados
from sqlalchemy import create_engine, text

URL_BANCO = "postgresql+psycopg2://postgres:root@localhost:5432/pergunteme_juri"

TEARDOWN_TABLES = """
DROP TABLE IF EXISTS document_chunks;
DROP TABLE IF EXISTS documents;
"""

def main() -> None:
    engine = create_engine(URL_BANCO, echo=True)
    with engine.connect() as conn:
        conn.execute(text(TEARDOWN_TABLES))
        conn.commit()


if __name__ == "__main__":
    main()