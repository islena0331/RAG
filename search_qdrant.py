import argparse
import json
import sys

from qdrant_client import models

from app.core.config import (
    EMBEDDING_MODEL_NAME,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)
from app.services.embedder import embed_texts, load_embedding_model
from app.storage.storage_qdrant import (
    collection_exists,
    get_collection_vector_size,
    get_qdrant_client,
)


# CLI 인자 설정
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Qdrant 벡터 검색 테스트")
    parser.add_argument("--query", required=True, help="검색 질문 또는 키워드")
    parser.add_argument("--top-k", type=int, default=5, help="검색 결과 개수")
    parser.add_argument(
        "--security-level",
        type=int,
        choices=(1, 2, 3),
        help="검색할 보안등급",
    )
    return parser


# 보안등급 필터 생성
def build_filter(security_level: int | None) -> models.Filter | None:
    if security_level is None:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(
                key="security_level",
                match=models.MatchValue(value=security_level),
            )
        ]
    )


# 검색 결과 출력
def print_results(points: list) -> None:
    if not points:
        print("검색 결과가 없습니다")
        return

    for index, point in enumerate(points, start=1):
        payload = point.payload or {}
        chunk_text = str(payload.get("chunk_text", ""))
        print(f"\n[{index}] score={point.score:.6f}")
        print(f"chunk_id: {payload.get('chunk_id')}")
        print(f"document_id: {payload.get('document_id')}")
        print(
            "page_numbers: "
            + json.dumps(payload.get("page_numbers", []), ensure_ascii=False)
        )
        print(f"security_level: {payload.get('security_level')}")
        print(
            "labels: "
            + json.dumps(payload.get("labels", []), ensure_ascii=False)
        )
        print(f"is_noisy: {payload.get('is_noisy')}")
        print(f"is_title: {payload.get('is_title')}")
        print(f"chunk_text: {chunk_text[:300]}")


# 벡터 검색 실행
def run(args: argparse.Namespace) -> None:
    if args.top_k <= 0:
        raise ValueError("--top-k는 1 이상이어야 합니다")

    client = get_qdrant_client()
    if not collection_exists(client, QDRANT_COLLECTION_NAME):
        raise ValueError(
            f"Qdrant collection이 없습니다: {QDRANT_COLLECTION_NAME}"
        )

    model = load_embedding_model()
    query_embeddings = embed_texts(model, [args.query])
    if not query_embeddings:
        raise ValueError("검색어 embedding 생성에 실패했습니다")

    query_vector = query_embeddings[0]
    collection_dimension = get_collection_vector_size(
        client,
        QDRANT_COLLECTION_NAME,
    )
    if len(query_vector) != collection_dimension:
        raise ValueError(
            f"검색 embedding dimension이 collection과 다릅니다: "
            f"query={len(query_vector)}, collection={collection_dimension}"
        )

    response = client.query_points(
        collection_name=QDRANT_COLLECTION_NAME,
        query=query_vector,
        query_filter=build_filter(args.security_level),
        limit=args.top_k,
        with_payload=True,
        with_vectors=False,
    )

    print(f"검색어: {args.query}")
    print(f"embedding model: {EMBEDDING_MODEL_NAME}")
    print(f"Qdrant: {QDRANT_URL}/{QDRANT_COLLECTION_NAME}")
    print_results(response.points)


def main() -> int:
    args = build_parser().parse_args()
    try:
        run(args)
        return 0
    except (ConnectionError, RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n사용자 요청으로 작업을 중단했습니다", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"오류: 검색 처리 중 예외가 발생했습니다: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
