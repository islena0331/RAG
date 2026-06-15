from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import CHUNK_OVERLAP, CHUNK_SIZE, MIN_CHUNK_LENGTH
from app.core.schemas import PageText, RagChunk
from app.services.chunking.deduplicator import remove_duplicate_drafts
from app.services.chunking.models import ChunkDraft, ChunkingResult, SkippedPage
from app.services.chunking.quality import (
    SHORT_CHUNK_THRESHOLD,
    is_noisy_text,
)
from app.services.chunking.splitter import PARAGRAPH_SEPARATOR, split_text


# 추출 방식 병합
def _merge_extraction_methods(methods: list[str]) -> str:
    unique_methods = list(dict.fromkeys(methods))
    return unique_methods[0] if len(unique_methods) == 1 else "+".join(unique_methods)


# 청크 초안 생성
def _page_drafts(
    page_texts: list[PageText],
    chunk_size: int,
    overlap: int,
    min_chunk_length: int,
) -> tuple[list[ChunkDraft], list[SkippedPage]]:
    drafts: list[ChunkDraft] = []
    skipped_pages: list[SkippedPage] = []
    quality_min_length = max(min_chunk_length, SHORT_CHUNK_THRESHOLD)

    for page in page_texts:
        text = page.text.strip()
        if not text:
            if page.extraction_method == "ocr_failed":
                reason = "image_only"
            elif page.extraction_method == "no_text":
                reason = "no_text"
            else:
                reason = "empty_after_cleaning"
            skipped_pages.append(SkippedPage(page.page_number, reason))
            continue

        if len(text) < SHORT_CHUNK_THRESHOLD:
            drafts.append(
                ChunkDraft(
                    text=text,
                    page_number=page.page_number,
                    page_numbers=[page.page_number],
                    extraction_method=page.extraction_method,
                )
            )
            continue

        page_chunks = split_text(
            text,
            chunk_size=chunk_size,
            overlap=overlap,
            min_chunk_length=quality_min_length,
        )
        if not page_chunks:
            skipped_pages.append(SkippedPage(page.page_number, "too_short"))
            continue

        drafts.extend(
            ChunkDraft(
                text=chunk_text,
                page_number=page.page_number,
                page_numbers=[page.page_number],
                extraction_method=page.extraction_method,
            )
            for chunk_text in page_chunks
        )

    return drafts, skipped_pages


# 짧은 청크 병합
def _merge_short_drafts(drafts: list[ChunkDraft]) -> list[ChunkDraft]:
    merged: list[ChunkDraft] = []
    index = 0

    while index < len(drafts):
        current = drafts[index]
        if len(current.text) >= SHORT_CHUNK_THRESHOLD or index + 1 >= len(drafts):
            merged.append(current)
            index += 1
            continue

        next_draft = drafts[index + 1]
        pages_are_adjacent = next_draft.page_number == current.page_numbers[-1] + 1
        if not pages_are_adjacent:
            merged.append(current)
            index += 1
            continue

        combined_text = (
            f"{current.text}{PARAGRAPH_SEPARATOR}{next_draft.text}".strip()
        )
        combined_pages = sorted(set(current.page_numbers + next_draft.page_numbers))
        combined = ChunkDraft(
            text=combined_text,
            page_number=next_draft.page_number,
            page_numbers=combined_pages,
            extraction_method=_merge_extraction_methods(
                [current.extraction_method, next_draft.extraction_method]
            ),
        )
        drafts[index + 1] = combined
        index += 1

    return merged


# 최종 청크 생성
def _to_rag_chunks(
    drafts: list[ChunkDraft],
    document_id: str,
    security_level: int,
    labels: list[str],
) -> list[RagChunk]:
    chunks: list[RagChunk] = []
    for index, draft in enumerate(drafts):
        chunks.append(
            RagChunk(
                chunk_id=str(uuid4()),
                document_id=document_id,
                chunk_index=index,
                chunk_text=draft.text,
                page_number=draft.page_number,
                page_numbers=list(draft.page_numbers),
                security_level=security_level,
                labels=list(labels),
                extraction_method=draft.extraction_method,
                is_noisy=is_noisy_text(draft.text),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    return chunks


# 청킹 파이프라인
def create_chunks_with_report(
    page_texts: list[PageText],
    document_id: str,
    security_level: int,
    labels: list[str],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_chunk_length: int = MIN_CHUNK_LENGTH,
) -> ChunkingResult:
    drafts, skipped_pages = _page_drafts(
        page_texts,
        chunk_size,
        overlap,
        min_chunk_length,
    )
    unique_page_drafts, page_duplicates = remove_duplicate_drafts(drafts)
    merged_drafts = _merge_short_drafts(unique_page_drafts)
    unique_drafts, merged_duplicates = remove_duplicate_drafts(merged_drafts)
    skipped_pages.extend(page_duplicates)
    skipped_pages.extend(merged_duplicates)
    skipped_pages.sort(key=lambda item: (item.page_number, item.reason))

    return ChunkingResult(
        chunks=_to_rag_chunks(
            unique_drafts,
            document_id=document_id,
            security_level=security_level,
            labels=labels,
        ),
        skipped_pages=skipped_pages,
    )


def create_chunks(
    page_texts: list[PageText],
    document_id: str,
    security_level: int,
    labels: list[str],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_chunk_length: int = MIN_CHUNK_LENGTH,
) -> list[RagChunk]:
    return create_chunks_with_report(
        page_texts=page_texts,
        document_id=document_id,
        security_level=security_level,
        labels=labels,
        chunk_size=chunk_size,
        overlap=overlap,
        min_chunk_length=min_chunk_length,
    ).chunks
