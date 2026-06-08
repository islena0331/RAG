from dataclasses import replace
from difflib import SequenceMatcher
import re

from app.services.chunking.models import ChunkDraft, SkippedPage


DATE_PATTERN = re.compile(
    r"\b(?:19|20)\d{2}[./-]\d{1,2}[./-]\d{1,2}\b"
    r"|\b\d{1,2}[./-]\d{1,2}[./-](?:19|20)?\d{2}\b"
)
TRAILING_PAGE_NUMBER = re.compile(r"(?:\s|^)(?:page\s*)?\d{1,3}\s*$", re.IGNORECASE)
NON_TEXT = re.compile(r"[^가-힣a-z0-9]+")


# 중복 비교용 정규화
def normalize_for_duplicate(text: str) -> str:
    normalized = text.lower()
    normalized = DATE_PATTERN.sub(" ", normalized)
    normalized = TRAILING_PAGE_NUMBER.sub(" ", normalized)
    normalized = NON_TEXT.sub(" ", normalized)
    return " ".join(normalized.split())


# 유사 중복 판정
def _is_near_duplicate(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True

    length_ratio = min(len(left), len(right)) / max(len(left), len(right))
    if length_ratio < 0.9:
        return False
    return SequenceMatcher(None, left, right).ratio() >= 0.96


# 중복 청크 제거
def remove_duplicate_drafts(
    drafts: list[ChunkDraft],
) -> tuple[list[ChunkDraft], list[SkippedPage]]:
    unique: list[ChunkDraft] = []
    normalized_unique: list[str] = []
    skipped: list[SkippedPage] = []

    for draft in drafts:
        normalized = normalize_for_duplicate(draft.text)
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(normalized_unique)
                if _is_near_duplicate(normalized, existing)
            ),
            None,
        )
        if duplicate_index is None:
            unique.append(draft)
            normalized_unique.append(normalized)
            continue

        kept = unique[duplicate_index]
        merged_pages = sorted(set(kept.page_numbers + draft.page_numbers))
        unique[duplicate_index] = replace(kept, page_numbers=merged_pages)
        for page_number in draft.page_numbers:
            skipped.append(SkippedPage(page_number=page_number, reason="duplicate"))

    return unique, skipped
