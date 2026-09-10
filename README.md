# PergunteMeJuri

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

Chatbot jurídico que responde perguntas sobre a legislação brasileira usando **RAG híbrido** — busca lexical e semântica combinadas — sobre PDFs de leis. Roda **inteiramente local**: nenhum dado sai da máquina e nenhuma API paga é usada.

O projeto foi construído para exercitar, ponta a ponta, as peças de um sistema RAG de verdade: indexação, recuperação híbrida, agente com memória, API em streaming e interface de chat.

---

## Pré-requisitos

| Ferramenta | Versão | Para quê |
|---|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | recente | Postgres, servidor MCP e API |
| [Ollama](https://ollama.com/) | recente | roda o LLM (fica **no host**, não em container, porque precisa da GPU) |
| [Node.js](https://nodejs.org/) | 20+ | frontend |
| Python | 3.12+ | apenas se for rodar o backend sem Docker |

A imagem do backend usa `torch` em versão **CPU-only**: os embeddings são leves e não precisam de GPU. Quem consome a GPU é o Ollama, no host.

---

## Subindo o projeto

### 1. Clone e configure

```bash
git clone <url-do-repositorio>
cd PergunteMeJuri
cp .env.example .env
```

O `.env` já vem com os valores padrão que funcionam localmente — não precisa editar nada para começar.

### 2. Baixe o modelo no Ollama

```bash
ollama pull qwen3:8b
```

Confirme que o Ollama está no ar: `curl http://localhost:11434/api/tags` deve listar o modelo.

### 3. Suba os containers

```bash
docker compose up -d --build
```

Sobem três serviços: `postgres_ia` (Postgres + pgvector), `hrag_mcp` (servidor MCP de busca) e `juri_api` (API HTTP).

> A primeira execução baixa o modelo de embedding (~500MB) dentro do container `hrag`. Ele fica num volume, então isso só acontece uma vez. O `healthcheck` do compose segura a API até o download terminar — se `docker compose ps` mostrar `hrag_mcp` como `starting`, é isso, aguarde.

### 4. Crie o schema do banco

```bash
docker compose exec api python -m backend.setup
```

Cria a extensão `vector`, as tabelas `documents` e `document_chunks`, o índice HNSW para busca vetorial e o índice GIN para busca textual.

### 5. Indexe os PDFs

```bash
docker compose exec hrag python -m backend.precompute_pipeline
```

Lê os PDFs de `backend/leis/`, limpa o texto, quebra em chunks de 256 tokens e grava conteúdo + embedding no Postgres. Para adicionar leis novas, jogue os PDFs nessa pasta e rode o comando de novo — chunks já indexados são ignorados por hash.

### 6. Suba o frontend

```bash
cd frontend
npm install
npm run dev
```

Abra **http://localhost:5173**.

### Verificando que está tudo de pé

```bash
curl http://localhost:8080/saude    # {"status":"ok"}
curl http://localhost:8080/leis     # {"leis":["constituição federal 1988"]}
```

### Recomeçando do zero

Para apagar o schema e reindexar tudo — útil depois de mexer no chunking ou no modelo de embedding:

```bash
docker compose exec api python -m backend.teardown
docker compose exec api python -m backend.setup
docker compose exec hrag python -m backend.precompute_pipeline
```

### Encerrando

```bash
docker compose down          # para os containers, preserva os dados
docker compose down -v       # apaga também o banco e os modelos baixados
```

---

## Rodando o backend sem Docker

Útil para desenvolver, porque o recarregamento é imediato.

```bash
python -m venv venv
source venv/Scripts/activate        # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt

docker compose up -d postgres       # só o banco em container
python -m backend.setup
python -m backend.precompute_pipeline
```

Depois, em dois terminais separados:

```bash
python -m backend.hrag              # servidor MCP  :8000
python -m backend.api               # API HTTP      :8080
```

> **Sempre use `python -m backend.x`, nunca `python backend/x.py`.** Os módulos importam `backend.config`, e a invocação direta não coloca a raiz do projeto no `sys.path`.

Para conversar pelo terminal, sem API nem frontend:

```bash
python -m backend.juri
```

---

## Problemas comuns

**`docker compose up` falha em `unable to get image`** — o Docker Desktop não está rodando.

**A API sobe e morre com `httpx.ConnectError: All connection attempts failed`** — ela não alcançou o Ollama ou o servidor MCP. Verifique com `docker compose exec api python -c "from backend import config as c; print(c.OLLAMA_BASE_URL, c.MCP_URL)"`. Dentro do container, o Ollama tem que ser `host.docker.internal`, nunca `localhost`.

**Mudei `OLLAMA_BASE_URL` no `.env` e o container parou de funcionar** — esperado. Essa variável vale para execução local. Para os containers use `OLLAMA_URL_DOCKER`, que existe justamente porque `localhost` significa coisas diferentes nos dois contextos.

**As respostas ignoram as leis e parecem "de cabeça"** — provavelmente nada foi indexado. Cheque com `curl http://localhost:8080/leis`; se vier vazio, rode o passo 5.

**Windows: `psycopg cannot use the 'ProactorEventLoop'`** — o psycopg3 assíncrono exige `SelectorEventLoop`. O projeto já trata isso em `backend/juri.py:fabrica_de_loop()`; o erro só aparece se você subir o uvicorn por fora, com `uvicorn backend.api:app`. Use `python -m backend.api`.

**Demora ~20s por resposta** — é o tempo de geração do `qwen3:8b` na sua GPU. Dá para reduzir com um modelo menor (`OLLAMA_MODEL` no `.env`).

---

## Arquitetura

```
                    ┌──────────────┐
                    │   Frontend   │  React + Vite + shadcn/ui
                    │    :5173     │
                    └──────┬───────┘
                           │  POST /perguntar  (SSE, token a token)
                    ┌──────▼───────┐
                    │  API FastAPI │  :8080
                    │              │
                    │  ┌────────┐  │
                    │  │ Juri   │  │  agente LangGraph
                    │  │ (grafo)│  │
                    │  └───┬────┘  │
                    └──────┼───────┘
                MCP        │        Ollama (host, GPU)
         ┌─────────────────┴──────────┐
         │                            │
  ┌──────▼──────┐             ┌───────▼──────┐
  │  hrag :8000 │             │  qwen3:8b    │
  │ servidor MCP│             │    :11434    │
  └──────┬──────┘             └──────────────┘
         │
  ┌──────▼──────────────────────────┐
  │ Postgres + pgvector             │
  │  documents / document_chunks    │  corpus indexado
  │  checkpoints / checkpoint_*     │  memória das conversas
  └─────────────────────────────────┘
```

### O caminho de uma pergunta

O agente é um grafo LangGraph de três nós:

```
START → rewrite → retrieve → generate → END
```

1. **`rewrite`** — transforma a pergunta numa consulta que se sustenta sozinha. *"E em quais casos ela é perdida?"* vira *"Em quais casos a nacionalidade brasileira pode ser perdida?"*. Sem isso, a busca recebe pronomes soltos e não recupera nada útil. É pulado na primeira pergunta da conversa, onde não há nada a resolver.
2. **`retrieve`** — chama a tool `search_laws` no servidor MCP e monta o contexto legal.
3. **`generate`** — o LLM responde usando apenas os trechos recuperados.

### Busca híbrida

A tool `search_laws` roda duas buscas independentes e funde os resultados:

- **Lexical**, com `tsvector`/`ts_rank` do Postgres e índice GIN. Boa em termos exatos: números de artigo, nomes de leis, jargão.
- **Semântica**, com `pgvector` e índice HNSW sobre embeddings do `multilingual-e5-small` (384 dimensões, distância de cosseno). Boa em paráfrase, quando a pergunta não usa as palavras do texto.

A fusão é por **Reciprocal Rank Fusion** (`score = Σ 1/(60 + posição)`), que combina rankings sem depender das escalas de score — o `ts_rank` e a similaridade de cosseno não são comparáveis diretamente. Um trecho que aparece bem colocado nas duas listas vence um que domina apenas uma delas.

Um detalhe que importa: a consulta lexical usa **OR** entre os termos, não o AND que o `plainto_tsquery` produz por padrão. Com AND, uma pergunta em linguagem natural exige que o mesmo chunk contenha todas as palavras, e o resultado é quase sempre vazio.

### Por que MCP

A busca é exposta como um **servidor MCP** (`backend/hrag.py`) em vez de ser importada como uma função. O custo é uma volta de rede de ~0,3s; o ganho é que a recuperação vira um serviço com contrato próprio, consumível por qualquer cliente MCP — outros agentes, o Claude Code, uma segunda aplicação — sem acoplar ninguém ao schema do banco. O `.mcp.json` na raiz permite conectar a base de leis diretamente ao Claude Code.

O servidor expõe:
- **tool `search_laws(query)`** — os trechos mais relevantes, com nome do documento e score;
- **resource `file://laws`** — os documentos indexados, que a API repassa em `GET /leis`.

### Memória

O checkpointer Postgres do LangGraph guarda o estado por `thread_id`, então a conversa sobrevive ao reinício do processo. O frontend guarda só o `thread_id` no `localStorage` e, ao abrir, confere o histórico com o servidor — se a thread não existir mais, descarta a sessão local em vez de exibir histórico fantasma.

Uma decisão de estado que vale destacar: **o contexto legal não fica em `messages`**. Tudo que entra ali é persistido e reenviado a cada turno, e os ~3k tokens de leis por pergunta estourariam a janela do modelo em poucas trocas — silenciosamente, porque o Ollama desliza a janela em vez de dar erro. O contexto vive num campo próprio do estado, sobrescrito a cada busca; o histórico persistido guarda apenas perguntas e respostas.

### API

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/perguntar` | pergunta e recebe a resposta em SSE |
| `GET` | `/conversas/{thread_id}` | histórico da conversa |
| `GET` | `/leis` | leis indexadas |
| `GET` | `/saude` | healthcheck |

O `/perguntar` emite eventos nomeados: `inicio` (com o `thread_id`, que o cliente guarda), `token`, `fim` e `erro`. O evento de erro existe porque, num stream, o status HTTP já foi enviado junto do primeiro byte — não há como devolver 500 depois que a resposta começou.

---

## Estrutura

```
backend/
  config.py               configuração central, lida do .env
  setup.py / teardown.py  cria e destrói o schema
  precompute_pipeline.py  extração dos PDFs, chunking, embeddings
  hrag.py                 servidor MCP: busca híbrida + RRF
  juri.py                 agente LangGraph (rewrite → retrieve → generate)
  api.py                  API FastAPI com streaming SSE
  leis/                   PDFs a indexar
frontend/
  src/lib/api.ts          cliente HTTP e parser de SSE
  src/lib/sessao.ts       persistência da sessão no navegador
  src/components/         cabeçalho, lista de mensagens, campo, modal de leis
compose.yml               Postgres + hrag + api
```

---

## Limitações conhecidas

- **O modelo ainda generaliza além do contexto.** Mesmo instruído a usar apenas os trechos recuperados, ele ocasionalmente acrescenta conclusões que não estão no texto legal. Mitigações naturais seriam exigir citação do artigo em cada afirmação, ou um nó de verificação confrontando a resposta com o contexto.
- **A reescrita custa uma chamada extra ao LLM** em toda pergunta de acompanhamento.
- **O corpus é pequeno** — apenas a Constituição Federal. A qualidade das respostas depende diretamente do que estiver em `backend/leis/`.
- **Sem autenticação.** Qualquer um com acesso à porta 8080 conversa com a API e lê qualquer `thread_id`.
- **Não é aconselhamento jurídico.** É um projeto de estudo sobre RAG.
