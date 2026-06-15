import argparse
import sys

from pymongo.errors import PyMongoError

from app.services.embedding_pipeline import embed_mongodb_chunks
from app.services.pipeline_presenter import print_embedding_summary


# CLI 인자 설정
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MongoDB chunk를 임베딩해 Qdrant에 저장합니다"
    )
    parser.add_argument(
        "--document-id",
        help="특정 document_id만 처리",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="처리할 최대 chunk 수",
    )
    parser.add_argument(
        "--include-noisy",
        action="store_true",
        help="is_noisy=true chunk 포함",
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


# 임베딩 실행
def run(args: argparse.Namespace) -> None:
    result = embed_mongodb_chunks(
        document_id=args.document_id,
        limit=args.limit,
        include_noisy=args.include_noisy,
        force=args.force,
        recreate=args.recreate_collection,
    )
    print_embedding_summary(result)


def main() -> int:
    args = build_parser().parse_args()
    try:
        run(args)
        return 0
    except (
        ConnectionError,
        PyMongoError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(
            "\n사용자 요청으로 작업을 중단했습니다",
            file=sys.stderr,
        )
        return 130
    except Exception as error:
        print(
            f"오류: 임베딩 처리 중 예외가 발생했습니다: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
