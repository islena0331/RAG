import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

from app.core.config import MONGODB_DB_NAME, MONGODB_URL
from app.core.schemas import DocumentMetadata, RagChunk
from app.services.chunker import SkippedPage, create_chunks_with_report
from app.services.file_validator import validate_pdf_file
from app.services.pdf_extractor import OCR_MODES, extract_pdf_pages
from app.services.text_cleaner import clean_page_texts
from app.storage.storage_json import save_to_json
from app.storage.storage_mongo import save_to_mongodb


STORAGE_MODES = ("json", "mongo", "both")


def security_level_type(value: str) -> int:
    try:
        security_level = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("보안 등급은 1, 2, 3 중 하나여야 합니다.") from error

    if security_level not in (1, 2, 3):
        raise argparse.ArgumentTypeError("보안 등급은 1, 2, 3 중 하나여야 합니다.")
    return security_level


def parse_labels(raw_labels: str) -> list[str]:
    return list(dict.fromkeys(label.strip() for label in raw_labels.split(",") if label.strip()))


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
    parser.add_argument("--ocr", choices=OCR_MODES, default="auto", help="OCR 모드")
    parser.add_argument(
        "--storage",
        choices=STORAGE_MODES,
        default="both",
        help="저장 대상",
    )
    return parser


# 결과 출력
def print_summary(
    document: DocumentMetadata,
    total_pages: int,
    extracted_pages: int,
    skipped_pages: list[SkippedPage],
    chunks: list[RagChunk],
    json_paths: tuple[Path, Path] | None,
    mongo_status: str,
    mongo_error: str | None,
) -> None:
    print("\n=== 처리 결과 ===")
    print(f"document_id: {document.document_id}")
    print(f"title: {document.title}")
    print(f"original_filename: {document.original_filename}")
    print(f"security_level: {document.security_level}")
    print(f"total_pages: {total_pages}")
    print(f"extracted_pages: {extracted_pages}")
    print(f"chunk_count: {len(chunks)}")
    print(f"noisy_chunk_count: {sum(chunk.is_noisy for chunk in chunks)}")
    print(f"title_chunk_count: {sum(chunk.is_title for chunk in chunks)}")
    print(
        "skipped_pages: "
        + json.dumps(
            [asdict(skipped_page) for skipped_page in skipped_pages],
            ensure_ascii=False,
        )
    )
    if json_paths:
        print(f"JSON document: {json_paths[0]}")
        print(f"JSON chunks: {json_paths[1]}")
    else:
        print("JSON 저장: 미실행")
    print(f"MongoDB 저장: {mongo_status}")
    if mongo_error:
        print(f"MongoDB 오류: {mongo_error}")
    print(f"MongoDB URL: {MONGODB_URL}")
    print(f"MongoDB DB: {MONGODB_DB_NAME}")


# 전처리 실행
def run_pipeline(args: argparse.Namespace) -> None:
    labels = parse_labels(args.labels)
    validated_file = validate_pdf_file(args.file)
    document_id = str(uuid4())
    document = DocumentMetadata(
        document_id=document_id,
        title=args.title.strip(),
        original_filename=validated_file["filename"],
        file_path=str(validated_file["path"]),
        file_type=validated_file["mime_type"],
        file_size=validated_file["size"],
        security_level=args.security_level,
        labels=labels,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    print(f"PDF 텍스트를 추출합니다: {validated_file['path']}")
    page_texts = extract_pdf_pages(validated_file["path"], args.ocr)
    cleaned_pages = clean_page_texts(page_texts)
    chunking_result = create_chunks_with_report(
        cleaned_pages,
        document_id=document_id,
        security_level=args.security_level,
        labels=labels,
    )
    chunks = chunking_result.chunks

    json_paths: tuple[Path, Path] | None = None
    if args.storage in ("json", "both"):
        json_paths = save_to_json(document, chunks)
        print("JSON 저장을 완료했습니다.")

    mongo_status = "미실행"
    mongo_error: str | None = None
    if args.storage in ("mongo", "both"):
        mongo_success, mongo_error = save_to_mongodb(document, chunks)
        mongo_status = "성공" if mongo_success else "실패"

    print_summary(
        document=document,
        total_pages=len(page_texts),
        extracted_pages=sum(bool(page.text.strip()) for page in page_texts),
        skipped_pages=chunking_result.skipped_pages,
        chunks=chunks,
        json_paths=json_paths,
        mongo_status=mongo_status,
        mongo_error=mongo_error,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if not args.title.strip():
            raise ValueError("문서 제목은 비어 있을 수 없습니다.")
        run_pipeline(args)
        return 0
    except (OSError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n사용자 요청으로 작업을 중단했습니다.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
