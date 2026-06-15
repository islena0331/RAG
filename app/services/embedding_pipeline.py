from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient, UpdateOne

from app.core.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL_NAME,
    EMBED_SKIP_NOISY,
    MONGODB_DB_NAME,
    MONGODB_URL,
    QDRANT_COLLECTION_NAME,
)
from app.services.embedder import (
    embed_texts,
    get_embedding_dimension,
    load_embedding_model,
)
from app.storage.storage_qdrant import (
    ensure_collection,
    get_qdrant_client,
    recreate_collection,
    upsert_chunks,
)


@dataclass
class EmbeddingSummary:
    total_chunks: int = 0
    selected_chunks: int = 0
    skipped_noisy_chunks: int = 0
    skipped_embedded_chunks: int = 0
    stored_chunks: int = 0
    failed_chunks: int = 0


@dataclass(frozen=True)
class EmbeddingPipelineResult:
    summary: EmbeddingSummary
    dimension: int | None


# MongoDB 청크 선택
def _select_chunks(
    collection: Any,
    *,
    document_id: str | None,
    limit: int | None,
    include_noisy: bool,
    force: bool,
    summary: EmbeddingSummary,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if document_id:
        query["document_id"] = document_id

    summary.total_chunks = collection.count_documents(query)
    selected: list[dict[str, Any]] = []
    skip_noisy = EMBED_SKIP_NOISY and not include_noisy
    cursor = collection.find(query).sort(
        [("document_id", 1), ("chunk_index", 1)]
    )

    for chunk in cursor:
        chunk_text = str(chunk.get("chunk_text", "")).strip()
        if not chunk_text:
            continue
        if skip_noisy and chunk.get("is_noisy") is True:
            summary.skipped_noisy_chunks += 1
            continue
        if (
            not force
            and chunk.get("embedded") is True
            and chunk.get("embedding_model") == EMBEDDING_MODEL_NAME
        ):
            summary.skipped_embedded_chunks += 1
            continue
        if limit is not None and len(selected) >= limit:
            break
        selected.append(chunk)

    summary.selected_chunks = len(selected)
    return selected


# 배치 실패 시 개별 임베딩 재시도
def _embed_chunks(
    model: Any,
    chunks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[list[float]], int]:
    embedded_chunks: list[dict[str, Any]] = []
    embeddings: list[list[float]] = []
    failed_count = 0

    for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[start : start + EMBEDDING_BATCH_SIZE]
        texts = [str(chunk["chunk_text"]) for chunk in batch]

        try:
            batch_embeddings = embed_texts(model, texts)
            if len(batch_embeddings) != len(batch):
                raise ValueError(
                    "embedding 결과 수가 chunk 수와 일치하지 않습니다"
                )
            embedded_chunks.extend(batch)
            embeddings.extend(batch_embeddings)
            continue
        except Exception as error:
            print(f"경고: batch 임베딩 실패, 개별 재시도: {error}")

        for chunk in batch:
            chunk_id = str(chunk.get("chunk_id", "알 수 없음"))
            try:
                embedding = embed_texts(
                    model,
                    [str(chunk["chunk_text"])],
                )
                if not embedding:
                    raise ValueError("빈 embedding 결과")
                embedded_chunks.append(chunk)
                embeddings.append(embedding[0])
            except Exception as error:
                failed_count += 1
                print(
                    f"경고: chunk 임베딩 실패: {chunk_id} / {error}"
                )

    return embedded_chunks, embeddings, failed_count


# MongoDB 임베딩 상태 갱신
def _update_mongodb_status(
    collection: Any,
    chunk_ids: list[str],
) -> None:
    if not chunk_ids:
        return

    embedded_at = datetime.now(timezone.utc).isoformat()
    operations = [
        UpdateOne(
            {"chunk_id": chunk_id},
            {
                "$set": {
                    "embedded": True,
                    "embedded_at": embedded_at,
                    "embedding_model": EMBEDDING_MODEL_NAME,
                    "vector_db": "qdrant",
                    "qdrant_collection": QDRANT_COLLECTION_NAME,
                    "vector_id": chunk_id,
                },
                "$unset": {"embedding": ""},
            },
        )
        for chunk_id in chunk_ids
    ]
    collection.bulk_write(operations, ordered=False)


# MongoDB 청크 임베딩과 Qdrant 저장
def embed_mongodb_chunks(
    *,
    document_id: str | None = None,
    limit: int | None = None,
    include_noisy: bool = False,
    force: bool = False,
    recreate: bool = False,
) -> EmbeddingPipelineResult:
    if limit is not None and limit <= 0:
        raise ValueError("--limit은 1 이상이어야 합니다")

    summary = EmbeddingSummary()
    dimension: int | None = None
    mongo_client = MongoClient(
        MONGODB_URL,
        serverSelectionTimeoutMS=5000,
    )

    try:
        mongo_client.admin.command("ping")
        chunk_collection = mongo_client[MONGODB_DB_NAME]["rag_chunks"]
        chunks = _select_chunks(
            chunk_collection,
            document_id=document_id,
            limit=limit,
            include_noisy=include_noisy,
            force=force,
            summary=summary,
        )
        if not chunks:
            return EmbeddingPipelineResult(summary, dimension)

        model = load_embedding_model()
        dimension = get_embedding_dimension(model)
        qdrant_client = get_qdrant_client()

        if recreate:
            recreate_collection(
                qdrant_client,
                QDRANT_COLLECTION_NAME,
                dimension,
            )
        else:
            ensure_collection(
                qdrant_client,
                QDRANT_COLLECTION_NAME,
                dimension,
            )

        embedded_chunks, embeddings, embedding_failures = _embed_chunks(
            model,
            chunks,
        )
        summary.failed_chunks += embedding_failures

        if embedded_chunks:
            result = upsert_chunks(
                client=qdrant_client,
                collection_name=QDRANT_COLLECTION_NAME,
                chunks=embedded_chunks,
                embeddings=embeddings,
                embedding_model=EMBEDDING_MODEL_NAME,
            )
            _update_mongodb_status(
                chunk_collection,
                result.succeeded_chunk_ids,
            )
            summary.stored_chunks = len(result.succeeded_chunk_ids)
            summary.failed_chunks += len(result.failed_chunks)
            for chunk_id, error in result.failed_chunks:
                print(
                    f"경고: Qdrant 저장 실패: {chunk_id} / {error}"
                )

        return EmbeddingPipelineResult(summary, dimension)
    finally:
        mongo_client.close()
