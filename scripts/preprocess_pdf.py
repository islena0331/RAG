import argparse
import sys

from app.core.cli import parse_labels, security_level_type
from app.services.document_pipeline import process_document
from app.services.pdf_extractor import OCR_MODES
from app.services.pipeline_presenter import print_document_summary


STORAGE_MODES = ("json", "mongo", "both")


# CLI 인자 설정
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="로컬 PDF를 RAG용 chunk로 전처리합니다."
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
        "--storage",
        choices=STORAGE_MODES,
        default="both",
        help="저장 대상",
    )
    return parser


# 전처리 실행
def run(args: argparse.Namespace) -> None:
    result = process_document(
        file_path=args.file,
        title=args.title,
        security_level=args.security_level,
        labels=parse_labels(args.labels),
        ocr_mode=args.ocr,
        storage=args.storage,
    )
    print_document_summary(result)


def main() -> int:
    args = build_parser().parse_args()
    try:
        run(args)
        return 0
    except (OSError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(
            "\n사용자 요청으로 작업을 중단했습니다.",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
