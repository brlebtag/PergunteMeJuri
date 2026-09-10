# Configuracao central do backend, carregada de variaveis de ambiente.
# Os valores padrao apontam para o ambiente de desenvolvimento local descrito
# no README; em container, sobrescreva pelo .env ou pelo compose.
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
RAIZ_DIR = BASE_DIR.parent

load_dotenv(RAIZ_DIR / ".env")


def _texto(nome: str, padrao: str) -> str:
    return os.getenv(nome, padrao)


def _inteiro(nome: str, padrao: int) -> int:
    valor = os.getenv(nome)
    return int(valor) if valor else padrao


def _decimal(nome: str, padrao: float) -> float:
    valor = os.getenv(nome)
    return float(valor) if valor else padrao


def _booleano(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "yes", "sim", "on")


# --- Banco de dados -------------------------------------------------------
POSTGRES_USER = _texto("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = _texto("POSTGRES_PASSWORD", "root")
POSTGRES_HOST = _texto("POSTGRES_HOST", "localhost")
POSTGRES_PORT = _inteiro("POSTGRES_PORT", 5432)
POSTGRES_DB = _texto("POSTGRES_DB", "pergunteme_juri")

# DATABASE_URL tem precedencia: e o formato que servicos gerenciados entregam.
URL_BANCO = _texto(
    "DATABASE_URL",
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)
SQL_ECHO = _booleano("SQL_ECHO")

# O checkpointer do LangGraph fala psycopg3 direto e nao entende o dialeto do
# SQLAlchemy, entao a mesma URL vai sem o sufixo "+psycopg2".
CHECKPOINT_URL = _texto("CHECKPOINT_URL", URL_BANCO.replace("+psycopg2", ""))

# --- Embeddings e chunking ------------------------------------------------
EMBEDDING_MODEL = _texto("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
CACHE_DIR = str(BASE_DIR / "modelos_cache")
DOC_FOLDER = str(BASE_DIR / _texto("DOC_FOLDER", "leis"))
CHUNK_SIZE = _inteiro("CHUNK_SIZE", 256)
OVERLAP = _decimal("OVERLAP", 0.15)

# O e5 e treinado de forma assimetrica: passagens e perguntas recebem prefixos
# diferentes. Sao acoplados ao modelo, entao nao viram variavel de ambiente.
PREFIX_PASSAGE = "passage: "
PREFIX_QUERY = "query: "

# --- Busca hibrida --------------------------------------------------------
LIMIT = _inteiro("RAG_LIMIT", 10)

# --- Servidor MCP (hrag.py) ----------------------------------------------
MCP_HOST = _texto("MCP_HOST", "localhost")
MCP_PORT = _inteiro("MCP_PORT", 8000)
MCP_URL = _texto("MCP_URL", f"http://{MCP_HOST}:{MCP_PORT}/mcp")

# --- API HTTP (api.py) ----------------------------------------------------
API_HOST = _texto("API_HOST", "0.0.0.0")
API_PORT = _inteiro("API_PORT", 8080)
# Origens liberadas no CORS, separadas por virgula. "*" libera todas.
CORS_ORIGINS = [
    o.strip() for o in _texto("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]

# --- LLM (juri.py) --------------------------------------------------------
OLLAMA_BASE_URL = _texto("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _texto("OLLAMA_MODEL", "qwen3:8b")
LLM_TEMPERATURE = _decimal("LLM_TEMPERATURE", 0.7)
# O padrao do Ollama (4096) cobre prompt + geracao, e o contexto legal sozinho
# ja passa de 3k tokens.
LLM_NUM_CTX = _inteiro("LLM_NUM_CTX", 8192)
# O qwen3 gera um bloco <think> descartado da saida: custa tempo e espaco na
# janela sem aparecer na resposta.
LLM_REASONING = _booleano("LLM_REASONING", False)
