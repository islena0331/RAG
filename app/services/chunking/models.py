from dataclasses import dataclass

from app.core.schemas import RagChunk


# 제외 페이지 구조
@dataclass(frozen=True)
class SkippedPage:
    page_number: int
    reason: str


@dataclass(frozen=True)
class ChunkingResult:
    chunks: list[RagChunk]
    skipped_pages: list[SkippedPage]


# 청크 초안 구조
@dataclass(frozen=True)
class ChunkDraft:
    text: str
    page_number: int
    page_numbers: list[int]
    extraction_method: str
    is_title: bool
