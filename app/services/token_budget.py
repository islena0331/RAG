from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import lru_cache
import math

from app.core.schemas import RetrievedChunk


@dataclass(frozen=True)
class ContextBudgetResult:
    sources: list[RetrievedChunk]
    excluded_sources: list[str]
    truncated_sources: list[str]
    token_count: int


# 토크나이저 로딩
@lru_cache(maxsize=8)
def _get_encoding(model_name: str):
    try:
        import tiktoken
    except ImportError:
        return None

    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        return tiktoken.get_encoding("o200k_base")


# 토큰 수 계산
def count_tokens(text: str, model_name: str) -> int:
    if not text:
        return 0

    encoding = _get_encoding(model_name)
    if encoding is not None:
        return len(encoding.encode(text))

    return max(1, math.ceil(len(text.encode("utf-8")) / 2))


# 토큰 기준 문자열 축약
def truncate_text(text: str, max_tokens: int, model_name: str) -> str:
    if max_tokens <= 0 or not text:
        return ""

    encoding = _get_encoding(model_name)
    if encoding is not None:
        token_ids = encoding.encode(text)
        if len(token_ids) <= max_tokens:
            return text
        return encoding.decode(token_ids[:max_tokens]).rstrip() + " …"

    byte_limit = max_tokens * 2
    encoded = text.encode("utf-8")
    if len(encoded) <= byte_limit:
        return text
    return encoded[:byte_limit].decode("utf-8", errors="ignore").rstrip() + " …"


# 문서 context 예산 적용
def fit_sources_to_budget(
    sources: list[RetrievedChunk],
    max_tokens: int,
    model_name: str,
    render_source: Callable[[RetrievedChunk], str],
) -> ContextBudgetResult:
    selected: list[RetrievedChunk] = []
    excluded: list[str] = []
    truncated: list[str] = []
    used_tokens = 0

    for index, source in enumerate(sources):
        rendered = render_source(source)
        source_tokens = count_tokens(rendered, model_name)

        if used_tokens + source_tokens <= max_tokens:
            selected.append(source)
            used_tokens += source_tokens
            continue

        if not selected:
            empty_source = replace(source, chunk_text="")
            metadata_tokens = count_tokens(render_source(empty_source), model_name)
            available_tokens = max_tokens - metadata_tokens - 8
            shortened_text = truncate_text(
                source.chunk_text,
                available_tokens,
                model_name,
            )
            if shortened_text:
                shortened_source = replace(source, chunk_text=shortened_text)
                shortened_tokens = count_tokens(
                    render_source(shortened_source),
                    model_name,
                )
                if shortened_tokens <= max_tokens:
                    selected.append(shortened_source)
                    truncated.append(source.source_id)
                    used_tokens = shortened_tokens

        excluded.extend(item.source_id for item in sources[index + 1 :])
        if not selected or selected[-1].source_id != source.source_id:
            excluded.insert(0, source.source_id)
        break

    return ContextBudgetResult(
        sources=selected,
        excluded_sources=excluded,
        truncated_sources=truncated,
        token_count=used_tokens,
    )
