from dataclasses import replace
import re
from typing import Any

from qdrant_client import models

from app.core.config import (
    QDRANT_COLLECTION_NAME,
    RAG_MAX_CHUNKS_PER_DOCUMENT,
)
from app.core.security_policy import (
    get_allowed_document_levels,
    is_access_allowed,
    validate_security_level,
)
from app.core.schemas import RetrievedChunk
from app.services.embedder import embed_texts, load_embedding_model
from app.storage.storage_qdrant import (
    collection_exists,
    get_collection_vector_size,
    get_qdrant_client,
)
from app.storage.storage_mongo import get_document_titles


# 중복 비교용 텍스트 정규화
def normalize_chunk_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return normalized


# payload boolean 변환
def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


# 페이지 번호 정리
def _normalize_page_numbers(payload: dict[str, Any]) -> list[int]:
    raw_pages = payload.get("page_numbers")
    if not isinstance(raw_pages, list):
        raw_pages = [payload.get("page_number")]

    pages: list[int] = []
    for value in raw_pages:
        try:
            page = int(value)
        except (TypeError, ValueError):
            continue
        if page > 0 and page not in pages:
            pages.append(page)
    return pages


# 라벨 정리
def _normalize_labels(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


# 보안 등급 필터 생성
def build_security_filter(user_security_level: int) -> models.Filter:
    allowed_levels = get_allowed_document_levels(user_security_level)
    return models.Filter(
        must=[
            models.FieldCondition(
                key="security_level",
                match=models.MatchAny(any=allowed_levels),
            )
        ]
    )


# 문서별 청크 수 조정
def limit_chunks_per_document(
    chunks: list[RetrievedChunk],
    top_k: int,
    max_chunks_per_document: int,
) -> list[RetrievedChunk]:
    if max_chunks_per_document <= 0:
        raise ValueError("RAG_MAX_CHUNKS_PER_DOCUMENT는 1 이상이어야 합니다.")

    selected: list[RetrievedChunk] = []
    deferred: list[RetrievedChunk] = []
    document_counts: dict[str, int] = {}

    for chunk in chunks:
        document_key = chunk.document_id or chunk.chunk_id
        current_count = document_counts.get(document_key, 0)
        if current_count < max_chunks_per_document:
            selected.append(chunk)
            document_counts[document_key] = current_count + 1
        else:
            deferred.append(chunk)

        if len(selected) >= top_k:
            return selected[:top_k]

    for chunk in deferred:
        selected.append(chunk)
        if len(selected) >= top_k:
            break

    return selected


class Retriever:
    def __init__(self) -> None:
        self._embedding_model: Any | None = None
        self._title_cache: dict[str, str] = {}

    # 임베딩 모델 단일 로딩
    def _get_embedding_model(self) -> Any:
        if self._embedding_model is None:
            self._embedding_model = load_embedding_model()
        return self._embedding_model

    # MongoDB 문서 제목 조회
    def _load_document_titles(self, document_ids: set[str]) -> None:
        missing_ids = {
            document_id
            for document_id in document_ids
            if document_id and document_id not in self._title_cache
        }
        if not missing_ids:
            return

        self._title_cache.update(get_document_titles(missing_ids))
        for document_id in missing_ids:
            self._title_cache.setdefault(document_id, document_id)

    # Qdrant 결과 변환
    def _convert_points(
        self,
        points: list[Any],
        include_noisy: bool,
        score_threshold: float | None,
        user_security_level: int,
    ) -> list[RetrievedChunk]:
        candidates: list[tuple[RetrievedChunk, str]] = []
        document_ids: set[str] = set()

        sorted_points = sorted(
            points,
            key=lambda point: float(point.score or 0.0),
            reverse=True,
        )
        for point in sorted_points:
            payload = point.payload or {}
            chunk_text = str(payload.get("chunk_text") or "").strip()
            if not chunk_text:
                continue
            if not include_noisy and _as_bool(payload.get("is_noisy", False)):
                continue

            score = float(point.score or 0.0)
            if score_threshold is not None and score < score_threshold:
                continue

            chunk_id = str(payload.get("chunk_id") or point.id)
            document_id = str(payload.get("document_id") or "")
            payload_title = str(
                payload.get("document_title") or payload.get("title") or ""
            ).strip()
            security_value = payload.get("security_level")
            if (
                isinstance(security_value, bool)
                or not isinstance(security_value, int)
                or not is_access_allowed(
                    user_security_level,
                    security_value,
                )
            ):
                continue
            security_level = security_value

            candidate = RetrievedChunk(
                source_id="",
                chunk_id=chunk_id,
                document_id=document_id,
                document_title=payload_title,
                chunk_text=chunk_text,
                page_numbers=_normalize_page_numbers(payload),
                score=score,
                security_level=security_level,
                labels=_normalize_labels(payload.get("labels")),
            )
            candidates.append((candidate, normalize_chunk_text(chunk_text)))
            if document_id and not payload_title:
                document_ids.add(document_id)

        self._load_document_titles(document_ids)

        deduplicated: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()
        seen_texts: set[str] = set()
        for candidate, normalized_text in candidates:
            if candidate.chunk_id in seen_chunk_ids:
                continue
            if normalized_text in seen_texts:
                continue

            title = candidate.document_title
            if not title:
                title = self._title_cache.get(
                    candidate.document_id,
                    candidate.document_id or "제목 없음",
                )
            deduplicated.append(replace(candidate, document_title=title))
            seen_chunk_ids.add(candidate.chunk_id)
            seen_texts.add(normalized_text)

        return deduplicated

    # 관련 청크 검색
    def retrieve(
        self,
        query: str,
        top_k: int,
        user_security_level: int,
        score_threshold: float | None = None,
        include_noisy: bool = False,
        max_chunks_per_document: int = RAG_MAX_CHUNKS_PER_DOCUMENT,
    ) -> list[RetrievedChunk]:
        normalized_query = re.sub(r"\s+", " ", query).strip()
        if not normalized_query:
            raise ValueError("질문을 입력해주세요.")
        validated_user_level = validate_security_level(user_security_level)
        if top_k <= 0:
            raise ValueError("--top-k는 1 이상이어야 합니다.")
        if score_threshold is not None and not -1.0 <= score_threshold <= 1.0:
            raise ValueError("--score-threshold는 -1과 1 사이여야 합니다.")

        client = get_qdrant_client()
        if not collection_exists(client, QDRANT_COLLECTION_NAME):
            raise ValueError(
                f"Qdrant collection이 없습니다: {QDRANT_COLLECTION_NAME}"
            )

        model = self._get_embedding_model()
        embeddings = embed_texts(model, [normalized_query])
        if not embeddings:
            raise RuntimeError("질문 임베딩 생성에 실패했습니다.")

        query_vector = embeddings[0]
        collection_dimension = get_collection_vector_size(
            client,
            QDRANT_COLLECTION_NAME,
        )
        if len(query_vector) != collection_dimension:
            raise ValueError(
                "질문 임베딩 차원과 Qdrant collection 차원이 다릅니다: "
                f"query={len(query_vector)}, collection={collection_dimension}"
            )

        candidate_limit = min(max(top_k * 4, top_k + 10), 100)
        try:
            response = client.query_points(
                collection_name=QDRANT_COLLECTION_NAME,
                query=query_vector,
                query_filter=build_security_filter(validated_user_level),
                limit=candidate_limit,
                with_payload=True,
                with_vectors=False,
                score_threshold=score_threshold,
            )
        except Exception as error:
            raise ConnectionError(
                f"Qdrant 검색에 실패했습니다: {error}"
            ) from error

        converted = self._convert_points(
            points=response.points,
            include_noisy=include_noisy,
            score_threshold=score_threshold,
            user_security_level=validated_user_level,
        )
        diversified = limit_chunks_per_document(
            chunks=converted,
            top_k=top_k,
            max_chunks_per_document=max_chunks_per_document,
        )
        return [
            replace(chunk, source_id=f"S{index}")
            for index, chunk in enumerate(diversified, start=1)
        ]
