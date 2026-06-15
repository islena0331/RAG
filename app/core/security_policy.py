VALID_SECURITY_LEVELS = (1, 2, 3)


# 보안등급 검증
def validate_security_level(level: int) -> int:
    if isinstance(level, bool) or not isinstance(level, int):
        raise ValueError("사용자 보안등급은 1, 2, 3 중 하나여야 합니다.")
    if level not in VALID_SECURITY_LEVELS:
        raise ValueError("사용자 보안등급은 1, 2, 3 중 하나여야 합니다.")
    return level


# 접근 가능 문서등급 계산
def get_allowed_document_levels(
    user_security_level: int,
) -> list[int]:
    validated_level = validate_security_level(user_security_level)
    return [
        level
        for level in VALID_SECURITY_LEVELS
        if level >= validated_level
    ]


# 문서 접근 허용 확인
def is_access_allowed(
    user_security_level: int,
    document_security_level: object,
) -> bool:
    try:
        validated_user_level = validate_security_level(user_security_level)
    except ValueError:
        return False

    if (
        isinstance(document_security_level, bool)
        or not isinstance(document_security_level, int)
        or document_security_level not in VALID_SECURITY_LEVELS
    ):
        return False

    return document_security_level >= validated_user_level
