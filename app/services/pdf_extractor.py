from collections.abc import Sequence
from pathlib import Path
import re
from statistics import median

from pdf2image import convert_from_path
from pypdf import PdfReader
import pytesseract
from pytesseract import Output

from app.core.config import POPPLER_PATH, TESSERACT_CMD
from app.core.schemas import PageText


OCR_MODES = ("off", "auto", "force")
MIN_PYPDF_TEXT_LENGTH = 30
OCR_DPI = 300
HANGUL_TOKEN = re.compile(r"^[가-힣]+$")
WORD_CHARACTER = re.compile(r"[가-힣A-Za-z0-9]")
MAX_DENSE_OCR_TOKENS = 700
MAX_SINGLE_HANGUL_RATIO = 0.75


class LowQualityOCRError(RuntimeError):
    pass


def _normalized_length(text: str) -> int:
    return len("".join(text.split()))


def _configure_ocr() -> str:
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)

    try:
        installed_languages: Sequence[str] = pytesseract.get_languages(config="")
    except Exception as error:
        print(f"경고: Tesseract 언어 목록을 확인하지 못했습니다: {error}")
        return "eng"

    if "kor" in installed_languages:
        return "eng+kor"

    print(
        "경고: Tesseract에 kor 언어 데이터가 없어 영어 OCR만 사용합니다. "
        "한국어 OCR 결과는 정확하지 않을 수 있습니다."
    )
    return "eng"


# OCR 단어 좌표 기반 문장 재구성
def _reconstruct_ocr_text(data: dict[str, list]) -> str:
    lines: dict[tuple[int, int, int], list[tuple[int, int, int, str]]] = {}

    for index, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        if not text:
            continue

        line_key = (
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        lines.setdefault(line_key, []).append(
            (
                data["left"][index],
                data["width"][index],
                data["height"][index],
                text,
            )
        )

    paragraphs: list[str] = []
    previous_paragraph: tuple[int, int] | None = None

    for line_key, words in lines.items():
        words.sort(key=lambda word: word[0])
        paragraph_key = line_key[:2]
        if previous_paragraph is not None and paragraph_key != previous_paragraph:
            paragraphs.append("")
        previous_paragraph = paragraph_key

        heights = [height for _, _, height, _ in words if height > 0]
        hangul_join_gap = max(4, round(median(heights) * 0.21)) if heights else 6
        line_text = ""
        previous_left = 0
        previous_width = 0
        previous_text = ""

        for left, width, _, text in words:
            if not line_text:
                line_text = text
            else:
                gap = left - (previous_left + previous_width)
                join_hangul = (
                    HANGUL_TOKEN.fullmatch(previous_text) is not None
                    and HANGUL_TOKEN.fullmatch(text) is not None
                    and gap <= hangul_join_gap
                )
                attach_punctuation = text[0] in ".,!?;:%)]}”’"
                follows_opening = previous_text[-1] in "([{“‘"

                separator = "" if join_hangul or attach_punctuation or follows_opening else " "
                line_text += f"{separator}{text}"

            previous_left = left
            previous_width = width
            previous_text = text

        paragraphs.append(line_text.strip())

    return "\n".join(paragraphs).strip()


# 복잡한 다단 문서 OCR 판정
def _is_low_quality_ocr(data: dict[str, list]) -> bool:
    tokens = [text.strip() for text in data["text"] if text.strip()]
    if len(tokens) < MAX_DENSE_OCR_TOKENS:
        return False

    hangul_tokens = [token for token in tokens if HANGUL_TOKEN.fullmatch(token)]
    if not hangul_tokens:
        return False

    single_hangul_ratio = (
        sum(len(token) == 1 for token in hangul_tokens) / len(hangul_tokens)
    )
    return single_hangul_ratio >= MAX_SINGLE_HANGUL_RATIO


# OCR 텍스트 품질 점수 계산
def _ocr_quality_score(text: str) -> float:
    compact_text = "".join(text.split())
    if not compact_text:
        return 0.0

    word_character_count = len(WORD_CHARACTER.findall(compact_text))
    readable_ratio = word_character_count / len(compact_text)
    tokens = re.findall(r"[가-힣]+", text)
    single_hangul_ratio = (
        sum(len(token) == 1 for token in tokens) / len(tokens)
        if tokens
        else 0.0
    )
    return readable_ratio - (single_hangul_ratio * 0.4)


def _extract_page_with_ocr(
    pdf_path: Path,
    page_number: int,
    language: str,
) -> str:
    images = convert_from_path(
        pdf_path,
        first_page=page_number,
        last_page=page_number,
        dpi=OCR_DPI,
        poppler_path=str(POPPLER_PATH),
    )
    if not images:
        return ""

    data = pytesseract.image_to_data(
        images[0],
        lang=language,
        config="--psm 3",
        output_type=Output.DICT,
    )
    if _is_low_quality_ocr(data):
        raise LowQualityOCRError(
            "복잡한 다단 이미지로 OCR 품질 기준을 충족하지 못했습니다"
        )
    return _reconstruct_ocr_text(data)


def _merge_extracted_text(pypdf_text: str, ocr_text: str) -> tuple[str, str]:
    if pypdf_text and ocr_text:
        if _normalized_length(pypdf_text) >= MIN_PYPDF_TEXT_LENGTH:
            return pypdf_text, "pypdf"
        if ocr_text in pypdf_text:
            return pypdf_text, "pypdf"
        if pypdf_text in ocr_text:
            return ocr_text, "ocr"

        if _ocr_quality_score(ocr_text) < 0.55:
            return pypdf_text, "pypdf"
        return f"{pypdf_text}\n\n{ocr_text}", "pypdf+ocr"
    if ocr_text:
        return ocr_text, "ocr"
    if pypdf_text:
        return pypdf_text, "pypdf"
    return "", "no_text"


def extract_pdf_pages(
    pdf_path: str | Path,
    ocr_mode: str = "auto",
) -> list[PageText]:
    if ocr_mode not in OCR_MODES:
        raise ValueError(f"OCR 모드는 {', '.join(OCR_MODES)} 중 하나여야 합니다.")

    path = Path(pdf_path).expanduser().resolve()
    try:
        reader = PdfReader(path)
    except Exception as error:
        raise ValueError(f"PDF 파일을 읽지 못했습니다: {error}") from error

    ocr_language: str | None = None
    page_texts: list[PageText] = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            pypdf_text = (page.extract_text() or "").strip()
        except Exception as error:
            print(f"경고: {page_number}페이지의 pypdf 텍스트 추출에 실패했습니다: {error}")
            pypdf_text = ""

        should_run_ocr = ocr_mode == "force" or (
            ocr_mode == "auto"
            and _normalized_length(pypdf_text) < MIN_PYPDF_TEXT_LENGTH
        )

        if not should_run_ocr:
            method = "pypdf" if pypdf_text else "no_text"
            page_texts.append(PageText(page_number, pypdf_text, method))
            continue

        if ocr_language is None:
            ocr_language = _configure_ocr()

        try:
            ocr_text = _extract_page_with_ocr(path, page_number, ocr_language)
            text, method = _merge_extracted_text(pypdf_text, ocr_text)
        except LowQualityOCRError as error:
            print(f"경고: {page_number}페이지 OCR 결과를 제외합니다: {error}")
            text = pypdf_text
            method = "pypdf" if pypdf_text else "ocr_failed"
        except Exception as error:
            print(f"경고: {page_number}페이지 OCR에 실패했습니다: {error}")
            text = pypdf_text
            method = "ocr_failed"

        page_texts.append(PageText(page_number, text, method))

    return page_texts
