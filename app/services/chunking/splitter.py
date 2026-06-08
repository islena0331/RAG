import re

from app.core.config import CHUNK_OVERLAP, CHUNK_SIZE, MIN_CHUNK_LENGTH


PARAGRAPH_SEPARATOR = "\n\n"


def _validate_options(
    chunk_size: int,
    overlap: int,
    min_chunk_length: int,
) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size는 1 이상이어야 합니다.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap은 0 이상이고 chunk_size보다 작아야 합니다.")
    if min_chunk_length <= 0:
        raise ValueError("min_chunk_length는 1 이상이어야 합니다.")


# 분할 위치 탐색
def _preferred_split_position(text: str, limit: int) -> int:
    minimum_boundary = max(1, int(limit * 0.6))
    candidates = (
        text.rfind("\n", minimum_boundary, limit + 1),
        text.rfind(". ", minimum_boundary, limit + 1),
        text.rfind("? ", minimum_boundary, limit + 1),
        text.rfind("! ", minimum_boundary, limit + 1),
        text.rfind(" ", minimum_boundary, limit + 1),
    )
    boundary = max(candidates)
    return boundary + 1 if boundary >= minimum_boundary else limit


def _tail_for_overlap(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    if len(text) <= overlap:
        return text

    start = len(text) - overlap
    boundary = text.find(" ", start)
    return text[boundary if boundary >= 0 else start :].strip()


# 긴 문단 분할
def _split_long_paragraph(
    paragraph: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    pieces: list[str] = []
    remaining = paragraph.strip()

    while len(remaining) > chunk_size:
        split_at = _preferred_split_position(remaining, chunk_size)
        piece = remaining[:split_at].strip()
        if piece:
            pieces.append(piece)

        safe_overlap = min(overlap, max(0, len(piece) - 1))
        overlap_text = _tail_for_overlap(piece, safe_overlap)
        remaining = f"{overlap_text} {remaining[split_at:].strip()}".strip()

    if remaining:
        pieces.append(remaining)
    return pieces


def _paragraph_units(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        normalized = paragraph.strip()
        if not normalized:
            continue
        if len(normalized) <= chunk_size:
            units.append(normalized)
        else:
            units.extend(_split_long_paragraph(normalized, chunk_size, overlap))
    return units


# 짧은 청크 병합
def _merge_short_chunks(
    chunks: list[str],
    min_chunk_length: int,
) -> list[str]:
    merged: list[str] = []
    pending = ""

    for chunk in chunks:
        if pending:
            chunk = f"{pending}{PARAGRAPH_SEPARATOR}{chunk}".strip()
            pending = ""
        if len(chunk) < min_chunk_length:
            pending = chunk
        else:
            merged.append(chunk)

    if pending and merged:
        merged[-1] = f"{merged[-1]}{PARAGRAPH_SEPARATOR}{pending}".strip()
    return merged


# 텍스트 분할
def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_chunk_length: int = MIN_CHUNK_LENGTH,
) -> list[str]:
    _validate_options(chunk_size, overlap, min_chunk_length)
    normalized_text = text.strip()
    if not normalized_text:
        return []

    units = _paragraph_units(normalized_text, chunk_size, overlap)
    chunks: list[str] = []
    current_parts: list[str] = []

    for unit in units:
        candidate = PARAGRAPH_SEPARATOR.join([*current_parts, unit]).strip()
        if not current_parts or len(candidate) <= chunk_size:
            current_parts.append(unit)
            continue

        completed = PARAGRAPH_SEPARATOR.join(current_parts).strip()
        chunks.append(completed)

        separator_length = len(PARAGRAPH_SEPARATOR) if overlap else 0
        available_overlap = max(0, chunk_size - len(unit) - separator_length)
        overlap_text = _tail_for_overlap(completed, min(overlap, available_overlap))
        current_parts = [part for part in (overlap_text, unit) if part]

    if current_parts:
        chunks.append(PARAGRAPH_SEPARATOR.join(current_parts).strip())

    return _merge_short_chunks(chunks, min_chunk_length)
