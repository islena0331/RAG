from dataclasses import dataclass


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str | None = None
    applied: bool = False


# 입력 guardrail 연결점
def check_input_guardrail(query: str) -> GuardResult:
    return GuardResult(allowed=True, applied=False)


# 출력 guardrail 연결점
def check_output_guardrail(answer: str) -> GuardResult:
    return GuardResult(allowed=True, applied=False)
