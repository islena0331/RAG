from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    title: str
    original_filename: str
    file_path: str
    file_type: str
    file_size: int
    security_level: int
    labels: list[str]
    created_at: str


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
    extraction_method: str


# 청크 구조
@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    chunk_text: str
    page_number: int
    page_numbers: list[int]
    security_level: int
    labels: list[str]
    extraction_method: str
    is_noisy: bool
    created_at: str


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    chunk_id: str
    document_id: str
    document_title: str
    chunk_text: str
    page_numbers: list[int]
    score: float
    security_level: int
    labels: list[str]


@dataclass(frozen=True)
class PromptBundle:
    developer_prompt: str
    user_prompt: str
    sources: list[RetrievedChunk]
    input_token_count: int
    context_token_count: int
    excluded_sources: list[str]
    truncated_sources: list[str]


@dataclass(frozen=True)
class LlmResult:
    answer: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    request_id: str | None


# dataclass 변환
def dataclass_to_dict(value: Any) -> dict[str, Any]:
    if not is_dataclass(value) or isinstance(value, type):
        raise TypeError("dataclass 인스턴스만 dict로 변환할 수 있습니다.")
    return asdict(value)
