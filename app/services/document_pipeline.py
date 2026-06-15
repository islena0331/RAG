from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.schemas import DocumentMetadata, RagChunk
from app.services.chunker import SkippedPage, create_chunks_with_report
from app.services.file_validator import validate_pdf_file
from app.services.pdf_extractor import extract_pdf_pages
from app.services.text_cleaner import clean_page_texts
from app.storage.storage_json import save_to_json
from app.storage.storage_mongo import save_to_mongodb


@dataclass(frozen=True)
class DocumentPipelineResult:
    document: DocumentMetadata
    total_pages: int
    extracted_pages: int
    skipped_pages: list[SkippedPage]
    chunks: list[RagChunk]
    json_paths: tuple[Path, Path] | None
    mongo_success: bool | None
    mongo_error: str | None


# PDF 전처리와 저장
def process_document(
    *,
    file_path: str,
    title: str,
    security_level: int,
    labels: list[str],
    ocr_mode: str,
    storage: str,
) -> DocumentPipelineResult:
    if storage not in ("json", "mongo", "both"):
        raise ValueError(f"지원하지 않는 저장 대상입니다: {storage}")

    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("문서 제목은 비어 있을 수 없습니다.")

    validated_file = validate_pdf_file(file_path)
    document = DocumentMetadata(
        document_id=str(uuid4()),
        title=normalized_title,
        original_filename=validated_file["filename"],
        file_path=str(validated_file["path"]),
        file_type=validated_file["mime_type"],
        file_size=validated_file["size"],
        security_level=security_level,
        labels=labels,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    print(f"PDF 텍스트를 추출합니다: {validated_file['path']}")
    page_texts = extract_pdf_pages(validated_file["path"], ocr_mode)
    cleaned_pages = clean_page_texts(page_texts)
    chunking_result = create_chunks_with_report(
        cleaned_pages,
        document_id=document.document_id,
        security_level=security_level,
        labels=labels,
    )

    json_paths: tuple[Path, Path] | None = None
    if storage in ("json", "both"):
        json_paths = save_to_json(document, chunking_result.chunks)
        print("JSON 저장을 완료했습니다.")

    mongo_success: bool | None = None
    mongo_error: str | None = None
    if storage in ("mongo", "both"):
        mongo_success, mongo_error = save_to_mongodb(
            document,
            chunking_result.chunks,
        )

    return DocumentPipelineResult(
        document=document,
        total_pages=len(page_texts),
        extracted_pages=sum(bool(page.text.strip()) for page in page_texts),
        skipped_pages=chunking_result.skipped_pages,
        chunks=chunking_result.chunks,
        json_paths=json_paths,
        mongo_success=mongo_success,
        mongo_error=mongo_error,
    )
