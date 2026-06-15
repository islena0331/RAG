import argparse
import sys

from pymongo.errors import PyMongoError

from app.core.cli import parse_labels, security_level_type
from app.services.document_pipeline import process_document
from app.services.embedding_pipeline import embed_mongodb_chunks
from app.services.pdf_extractor import OCR_MODES
from app.services.pipeline_presenter import (
    print_document_summary,
    print_embedding_summary,
)


# CLI 인자 설정
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "PDF 전처리, MongoDB 저장, 임베딩, Qdrant 저장을 "
            "순서대로 실행합니다"
        )
    )
    parser.add_argument("--file", required=True, help="처리할 PDF 파일 경로")
    parser.add_argument("--title", required=True, help="문서 제목")
    parser.add_argument(
        "--security-level",
        required=True,
        type=security_level_type,
        help="문서 보안 등급: 1, 2, 3",
    )
    parser.add_argument("--labels", default="", help="쉼표로 구분한 라벨")
    parser.add_argument(
        "--ocr",
        choices=OCR_MODES,
        default="auto",
        help="OCR 모드",
    )
    parser.add_argument(
        "--include-noisy",
        action="store_true",
        help="is_noisy=true chunk도 임베딩",
    )
    return parser


# 전체 적재 파이프라인
def run(args: argparse.Namespace) -> None:
    document_result = process_document(
        file_path=args.file,
        title=args.title,
        security_level=args.security_level,
        labels=parse_labels(args.labels),
        ocr_mode=args.ocr,
        storage="both",
    )
    print_document_summary(document_result)

    if document_result.mongo_success is not True:
        raise RuntimeError(
            "MongoDB 저장 실패로 임베딩을 실행하지 않습니다"
        )

    embedding_result = embed_mongodb_chunks(
        document_id=document_result.document.document_id,
        include_noisy=args.include_noisy,
    )
    print_embedding_summary(embedding_result)

    if embedding_result.summary.failed_chunks:
        raise RuntimeError(
            "일부 chunk의 임베딩 또는 Qdrant 저장에 실패했습니다"
        )
    if embedding_result.summary.stored_chunks == 0:
        raise RuntimeError(
            "Qdrant에 저장된 chunk가 없습니다. "
            "noisy chunk만 있다면 --include-noisy를 사용해주세요"
        )

    print("\n전체 적재 파이프라인을 완료했습니다.")


def main() -> int:
    args = build_parser().parse_args()
    try:
        run(args)
        return 0
    except (
        ConnectionError,
        OSError,
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
            f"오류: 전체 적재 중 예외가 발생했습니다: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
