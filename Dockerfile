FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence-transformers

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-rag.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-rag.txt

ARG EMBEDDING_MODEL_NAME=BAAI/bge-m3
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL_NAME}')"

COPY . .

CMD ["python", "rag_answer.py", "--help"]
