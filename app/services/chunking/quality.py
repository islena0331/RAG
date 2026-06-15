from collections import Counter
import re


SHORT_CHUNK_THRESHOLD = 100
STRUCTURE_DELIMITER = re.compile(r"[,;|/\\]")
NUMBER_TOKEN = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)")
WORD_TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")
KOREAN_NAME_WITH_NUMBER = re.compile(r"[가-힣]{2,4}\s*\(\d{2,4}\)")


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
