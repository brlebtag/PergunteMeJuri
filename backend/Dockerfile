FROM python:3.12-slim

WORKDIR /app

# O sentence-transformers puxa o torch, que por padrao vem com CUDA (~2.5GB).
# Aqui os embeddings rodam em CPU: a variante cpu-only corta a imagem para
# uma fracao disso. Instalado antes do requirements.txt para que o pip veja a
# dependencia ja satisfeita.
RUN pip install --no-cache-dir torch==2.14.0 \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# Modelo e tokenizer sao baixados na primeira execucao e ficam no volume
# declarado no compose, para nao repetir o download a cada rebuild.
ENV HF_HOME=/app/backend/modelos_cache \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "backend.api"]
