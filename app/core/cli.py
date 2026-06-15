import argparse


# 보안 등급 검증
def security_level_type(value: str) -> int:
    try:
        security_level = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "보안 등급은 1, 2, 3 중 하나여야 합니다."
        ) from error

    if security_level not in (1, 2, 3):
        raise argparse.ArgumentTypeError(
            "보안 등급은 1, 2, 3 중 하나여야 합니다."
        )
    return security_level


# 라벨 파싱
def parse_labels(raw_labels: str) -> list[str]:
    return list(
        dict.fromkeys(
            label.strip()
            for label in raw_labels.split(",")
            if label.strip()
        )
    )
