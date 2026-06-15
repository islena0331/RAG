from dataclasses import dataclass
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient, models

from app.core.config import QDRANT_COLLECTION_NAME, QDRANT_URL


PAYLOAD_FIELDS = (
    "chunk_id",
    "document_id",
    "chunk_index",
    "chunk_text",
    "page_number",
    "page_numbers",
    "security_level",
    "labels",
    "extraction_method",
    "is_noisy",
    "created_at",
)


@dataclass(frozen=True)
class QdrantUpsertResult:
    succeeded_chunk_ids: list[str]
    failed_chunks: list[tuple[str, str]]


# Qdrant 클라이언트 생성
def get_qdrant_client(url: str = QDRANT_URL) -> QdrantClient:
    client = QdrantClient(url=url, timeout=30)
    try:
        client.get_collections()
    except Exception as error:
        raise ConnectionError(f"Qdrant 연결에 실패했습니다: {url} / {error}") from error
    return client


# 컬렉션 존재 확인
def collection_exists(
    client: QdrantClient,
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> bool:
    return client.collection_exists(collection_name)



# 컬렉션 벡터 차원 확인
def get_collection_vector_size(
    client: QdrantClient,
    collection_name: str,
) -> int:
    collection = client.get_collection(collection_name)
    vectors_config = collection.config.params.vectors

    if isinstance(vectors_config, dict):
        if len(vectors_config) != 1:
            raise ValueError("이름이 여러 개인 벡터 컬렉션은 지원하지 않습니다")
        vectors_config = next(iter(vectors_config.values()))

    vector_size = getattr(vectors_config, "size", None)
    if vector_size is None:
        raise ValueError("Qdrant collection의 vector size를 확인할 수 없습니다")
    return int(vector_size)


# 컬렉션 생성과 차원 검증
def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    if collection_exists(client, collection_name):
        existing_size = get_collection_vector_size(client, collection_name)
        if existing_size != vector_size:
            raise ValueError(
                f"Qdrant collection vector size가 일치하지 않습니다: "
                f"기존={existing_size}, 현재={vector_size}"
            )
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )


# 컬렉션 재생성
def recreate_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    if collection_exists(client, collection_name):
        client.delete_collection(collection_name)
    ensure_collection(client, collection_name, vector_size)


# Qdrant payload 생성
def _build_payload(chunk: dict[str, Any], embedding_model: str) -> dict[str, Any]:
    payload = {field: chunk.get(field) for field in PAYLOAD_FIELDS}
    payload["embedding_model"] = embedding_model
    return payload


# Point 생성
def _build_point(
    chunk: dict[str, Any],
    embedding: list[float],
    embedding_model: str,
) -> models.PointStruct:
    chunk_id = str(chunk["chunk_id"])
    point_id = str(UUID(chunk_id))
    return models.PointStruct(
        id=point_id,
        vector=embedding,
        payload=_build_payload(chunk, embedding_model),
    )


# 청크 벡터 저장
def upsert_chunks(
    client: QdrantClient,
    collection_name: str,
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
    embedding_model: str,
) -> QdrantUpsertResult:
    if len(chunks) != len(embeddings):
        raise ValueError("chunk 수와 embedding 수가 일치하지 않습니다")

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    try:
        points = [
            _build_point(chunk, embedding, embedding_model)
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        client.upsert(collection_name=collection_name, points=points, wait=True)
        succeeded.extend(str(chunk["chunk_id"]) for chunk in chunks)
        return QdrantUpsertResult(succeeded, failed)
    except Exception:
        pass

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        chunk_id = str(chunk.get("chunk_id", "알 수 없음"))
        try:
            point = _build_point(chunk, embedding, embedding_model)
            client.upsert(
                collection_name=collection_name,
                points=[point],
                wait=True,
            )
            succeeded.append(chunk_id)
        except Exception as error:
            failed.append((chunk_id, str(error)))

    return QdrantUpsertResult(succeeded, failed)
