from dataclasses import asdict
import json

from app.core.config import (
    EMBEDDING_MODEL_NAME,
    MONGODB_DB_NAME,
    MONGODB_URL,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)
from app.services.document_pipeline import DocumentPipelineResult
from app.services.embedding_pipeline import EmbeddingPipelineResult


# 문서 처리 결과 출력
def print_document_summary(result: DocumentPipelineResult) -> None:
    document = result.document
    print("\n=== 문서 처리 결과 ===")
    print(f"document_id: {document.document_id}")
    print(f"title: {document.title}")
    print(f"original_filename: {document.original_filename}")
    print(f"security_level: {document.security_level}")
    print(f"total_pages: {result.total_pages}")
    print(f"extracted_pages: {result.extracted_pages}")
    print(f"chunk_count: {len(result.chunks)}")
    print(
        "noisy_chunk_count: "
        f"{sum(chunk.is_noisy for chunk in result.chunks)}"
    )
    print(
        "skipped_pages: "
        + json.dumps(
            [
                asdict(skipped_page)
                for skipped_page in result.skipped_pages
            ],
            ensure_ascii=False,
        )
    )
    if result.json_paths:
        print(f"JSON document: {result.json_paths[0]}")
        print(f"JSON chunks: {result.json_paths[1]}")
    else:
        print("JSON 저장: 미실행")

    if result.mongo_success is None:
        mongo_status = "미실행"
    else:
        mongo_status = "성공" if result.mongo_success else "실패"
    print(f"MongoDB 저장: {mongo_status}")
    if result.mongo_error:
        print(f"MongoDB 오류: {result.mongo_error}")
    print(f"MongoDB URL: {MONGODB_URL}")
    print(f"MongoDB DB: {MONGODB_DB_NAME}")


# 임베딩 결과 출력
def print_embedding_summary(
    result: EmbeddingPipelineResult,
) -> None:
    summary = result.summary
    print("\n=== 임베딩 결과 ===")
    print(f"MongoDB URL: {MONGODB_URL}")
    print(f"MongoDB DB: {MONGODB_DB_NAME}")
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Qdrant collection: {QDRANT_COLLECTION_NAME}")
    print(f"embedding model: {EMBEDDING_MODEL_NAME}")
    print(
        "embedding dimension: "
        f"{result.dimension if result.dimension else '미확인'}"
    )
    print(f"전체 chunk 수: {summary.total_chunks}")
    print(f"선택된 chunk 수: {summary.selected_chunks}")
    print(f"제외 noisy chunk 수: {summary.skipped_noisy_chunks}")
    print(
        "이미 embedded인 chunk 수: "
        f"{summary.skipped_embedded_chunks}"
    )
    print(f"Qdrant 저장 성공 chunk 수: {summary.stored_chunks}")
    print(f"실패 chunk 수: {summary.failed_chunks}")
