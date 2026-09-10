# Cria banco de dados
import os
from sqlalchemy import create_engine, text

from backend.config import SQL_ECHO, URL_BANCO

TEARDOWN_TABLES = """
DROP TABLE IF EXISTS document_chunks;
DROP TABLE IF EXISTS documents;
"""

def main() -> None:
    engine = create_engine(URL_BANCO, echo=SQL_ECHO)
    with engine.connect() as conn:
        conn.execute(text(TEARDOWN_TABLES))
        conn.commit()


if __name__ == "__main__":
    main()