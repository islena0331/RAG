import re


DOCUMENT_KEYWORDS = {
    "문서",
    "자료",
    "보고서",
    "강의",
    "슬라이드",
    "페이지",
    "출처",
    "근거",
    "요약",
    "핵전략",
    "핵위협",
    "북한",
    "전략",
    "정책",
    "법제화",
    "군사",
}
CASUAL_KEYWORDS = {
    "밥",
    "메뉴",
    "먹을까",
    "먹지",
    "점심",
    "저녁",
    "아침",
    "간식",
    "맛집",
    "날씨",
    "기분",
    "심심",
    "농담",
    "인사",
    "안녕",
}
DOCUMENT_COMMANDS = {
    "알려줘",
    "설명",
    "요약",
    "정리",
    "근거",
    "비교",
    "찾아",
    "검색",
    "무엇",
    "뭐야",
}


# 질문 정규화
def normalize_question(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip().lower()


# 문서 검색 생략 판단
def should_skip_retrieval(query: str) -> bool:
    normalized = normalize_question(query)
    if not normalized:
        return False

    if any(keyword in normalized for keyword in DOCUMENT_KEYWORDS):
        return False

    casual_hit = any(keyword in normalized for keyword in CASUAL_KEYWORDS)
    command_hit = any(command in normalized for command in DOCUMENT_COMMANDS)
    return casual_hit and not command_hit
