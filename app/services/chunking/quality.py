from collections import Counter
import re


SHORT_CHUNK_THRESHOLD = 100
STRUCTURE_DELIMITER = re.compile(r"[,;|/\\]")
NUMBER_TOKEN = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)")
WORD_TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")
KOREAN_NAME_WITH_NUMBER = re.compile(r"[가-힣]{2,4}\s*\(\d{2,4}\)")
TITLE_KEYWORD = re.compile(
    r"(?:제\d+[장절]|목차|제목|주제|리포트|보고서|강의|수업|순서|개요|"
    r"평가|대응태세|핵심\s*내용|작성\s*방법|출처)"
)
COMMON_WORDS = {
    "그리고",
    "대한",
    "관련",
    "내용",
    "위한",
    "이번",
    "페이지",
    "최근",
}


# 의미 단어 추출
def meaningful_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in WORD_TOKEN.findall(text)
        if len(token) >= 2 and token.lower() not in COMMON_WORDS
    }


# 제목 판정
def is_title_text(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized or len(normalized) >= SHORT_CHUNK_THRESHOLD:
        return False

    sentence_endings = len(re.findall(r"[.!?。！？]", normalized))
    word_count = len(WORD_TOKEN.findall(normalized))
    return bool(TITLE_KEYWORD.search(normalized)) or (
        sentence_endings <= 1 and word_count <= 18
    )


# 짧은 청크 병합 판정
def should_merge_short_with_next(short_text: str, next_text: str) -> bool:
    if not is_title_text(short_text):
        return True

    short_tokens = meaningful_tokens(short_text)
    next_tokens = meaningful_tokens(next_text[:500])
    shared_tokens = short_tokens & next_tokens

    required_overlap = 1 if len(short_tokens) <= 4 else 2
    return len(shared_tokens) >= required_overlap


# noisy 판정
def is_noisy_text(text: str) -> bool:
    compact_text = "".join(text.split())
    if not compact_text:
        return False

    tokens = WORD_TOKEN.findall(text)
    if not tokens:
        return False

    token_counts = Counter(token.lower() for token in tokens)
    repeated_token_count = sum(count - 1 for count in token_counts.values())
    repeated_token_ratio = repeated_token_count / len(tokens)
    single_character_ratio = sum(len(token) == 1 for token in tokens) / len(tokens)
    delimiter_count = len(STRUCTURE_DELIMITER.findall(compact_text))
    number_count = len(NUMBER_TOKEN.findall(compact_text))
    digit_count = sum(character.isdigit() for character in compact_text)
    digit_ratio = digit_count / len(compact_text)
    sentence_count = len(re.findall(r"[.!?。！？]", text))
    roster_entry_count = len(KOREAN_NAME_WITH_NUMBER.findall(text))

    roster_like = roster_entry_count >= 5
    numeric_table_like = (
        number_count >= 20 and digit_ratio >= 0.22 and sentence_count <= 3
    )
    repeated_pattern_like = (
        len(tokens) >= 25
        and repeated_token_ratio >= 0.4
        and delimiter_count >= 10
        and sentence_count <= 3
    )
    broken_ocr_like = (
        len(tokens) >= 20
        and single_character_ratio >= 0.6
        and sentence_count <= 2
    )
    return roster_like or numeric_table_like or repeated_pattern_like or broken_ocr_like
