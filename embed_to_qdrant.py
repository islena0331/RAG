import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import sys
from typing import Any

from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

from app.core.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL_NAME,
    EMBED_SKIP_NOISY,
    EMBED_SKIP_TITLE,
    MONGODB_DB_NAME,
    MONGODB_URL,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
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
    skipped_title_chunks: int = 0
    skipped_embedded_chunks: int = 0
    stored_chunks: int = 0
    failed_chunks: int = 0


# CLI 인자 설정
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MongoDB chunk를 임베딩해 Qdrant에 저장합니다"
    )
    parser.add_argument("--document-id", help="특정 document_id만 처리")
    parser.add_argument("--limit", type=int, help="처리할 최대 chunk 수")
    parser.add_argument(
        "--include-noisy",
        action="store_true",
        help="is_noisy=true chunk 포함",
    )
    parser.add_argument(
        "--include-title",
        action="store_true",
        help="is_title=true chunk 포함",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="이미 임베딩된 chunk 재처리",
    )
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Qdrant collection 삭제 후 재생성",
    )
    return parser


# MongoDB chunk 선택
def select_chunks(
    collection: Any,
    args: argparse.Namespace,
    summary: EmbeddingSummary,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if args.document_id:
        query["document_id"] = args.document_id

    summary.total_chunks = collection.count_documents(query)
    selected: list[dict[str, Any]] = []
    skip_noisy = EMBED_SKIP_NOISY and not args.include_noisy
    skip_title = EMBED_SKIP_TITLE and not args.include_title

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
        if skip_title and chunk.get("is_title") is True:
            summary.skipped_title_chunks += 1
            continue
        if (
            not args.force
            and chunk.get("embedded") is True
            and chunk.get("embedding_model") == EMBEDDING_MODEL_NAME
        ):
            summary.skipped_embedded_chunks += 1
            continue
        if args.limit is not None and len(selected) >= args.limit:
            continue
        selected.append(chunk)

    summary.selected_chunks = len(selected)
    return selected


# batch 실패 시 개별 임베딩 재시도
def embed_chunks(
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
                raise ValueError("embedding 결과 수가 chunk 수와 일치하지 않습니다")
            embedded_chunks.extend(batch)
            embeddings.extend(batch_embeddings)
            continue
        except Exception as error:
            print(f"경고: batch 임베딩 실패, 개별 재시도: {error}")

        for chunk in batch:
            chunk_id = str(chunk.get("chunk_id", "알 수 없음"))
            try:
                embedding = embed_texts(model, [str(chunk["chunk_text"])])
                if not embedding:
                    raise ValueError("빈 embedding 결과")
                embedded_chunks.append(chunk)
                embeddings.append(embedding[0])
            except Exception as error:
                failed_count += 1
                print(f"경고: chunk 임베딩 실패: {chunk_id} / {error}")

    return embedded_chunks, embeddings, failed_count


# MongoDB 임베딩 상태 업데이트
def update_mongodb_status(
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


# 실행 결과 출력
def print_summary(summary: EmbeddingSummary, dimension: int | None) -> None:
    print("\n=== 임베딩 결과 ===")
    print(f"MongoDB URL: {MONGODB_URL}")
    print(f"MongoDB DB: {MONGODB_DB_NAME}")
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Qdrant collection: {QDRANT_COLLECTION_NAME}")
    print(f"embedding model: {EMBEDDING_MODEL_NAME}")
    print(f"embedding dimension: {dimension if dimension else '미확인'}")
    print(f"전체 chunk 수: {summary.total_chunks}")
    print(f"선택된 chunk 수: {summary.selected_chunks}")
    print(f"제외 noisy chunk 수: {summary.skipped_noisy_chunks}")
    print(f"제외 title chunk 수: {summary.skipped_title_chunks}")
    print(f"이미 embedded인 chunk 수: {summary.skipped_embedded_chunks}")
    print(f"Qdrant 저장 성공 chunk 수: {summary.stored_chunks}")
    print(f"실패 chunk 수: {summary.failed_chunks}")


# 임베딩 파이프라인
def run(args: argparse.Namespace) -> None:
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit은 1 이상이어야 합니다")

    summary = EmbeddingSummary()
    mongo_client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    dimension: int | None = None

    try:
        mongo_client.admin.command("ping")
        chunk_collection = mongo_client[MONGODB_DB_NAME]["rag_chunks"]
        chunks = select_chunks(chunk_collection, args, summary)
        if not chunks:
            print_summary(summary, dimension)
            return

        model = load_embedding_model()
        dimension = get_embedding_dimension(model)
        qdrant_client = get_qdrant_client()

        if args.recreate_collection:
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

        embedded_chunks, embeddings, embedding_failures = embed_chunks(
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
            update_mongodb_status(
                chunk_collection,
                result.succeeded_chunk_ids,
            )
            summary.stored_chunks = len(result.succeeded_chunk_ids)
            summary.failed_chunks += len(result.failed_chunks)
            for chunk_id, error in result.failed_chunks:
                print(f"경고: Qdrant 저장 실패: {chunk_id} / {error}")

        print_summary(summary, dimension)
    finally:
        mongo_client.close()


def main() -> int:
    args = build_parser().parse_args()
    try:
        run(args)
        return 0
    except (ConnectionError, PyMongoError, RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n사용자 요청으로 작업을 중단했습니다", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"오류: 임베딩 처리 중 예외가 발생했습니다: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
