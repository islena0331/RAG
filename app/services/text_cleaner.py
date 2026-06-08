import re

from app.core.schemas import PageText


CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MULTIPLE_SPACES = re.compile(r"[^\S\r\n]+")
MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:"
    r"\d{1,3}"
    r"|[-–—]\s*\d{1,4}\s*[-–—]"
    r"|page\s+\d{1,4}(?:\s+of\s+\d{1,4})?"
    r"|페이지\s*\d{1,4}"
    r")\s*$",
    re.IGNORECASE,
)


# 페이지 번호 제거
def _remove_page_number_lines(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not PAGE_NUMBER_LINE.fullmatch(line)
    )


# 문단 정리
def _normalize_paragraphs(text: str) -> str:
    paragraphs: list[str] = []

    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        paragraph = MULTIPLE_SPACES.sub(" ", " ".join(lines)).strip()
        if paragraph:
            paragraphs.append(paragraph)

    return "\n\n".join(paragraphs)


# 텍스트 정리
def clean_text(text: str) -> str:
    cleaned = text.replace("\x00", "")
    cleaned = CONTROL_CHARACTERS.sub("", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = MULTIPLE_SPACES.sub(" ", cleaned)
    cleaned = _remove_page_number_lines(cleaned)
    cleaned = MULTIPLE_NEWLINES.sub("\n\n", cleaned)
    return _normalize_paragraphs(cleaned)


def clean_page_texts(page_texts: list[PageText]) -> list[PageText]:
    return [
        PageText(
            page_number=page.page_number,
            text=clean_text(page.text),
            extraction_method=page.extraction_method,
        )
        for page in page_texts
    ]
