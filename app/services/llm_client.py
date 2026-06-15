from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MAX_RETRIES,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS,
)
from app.core.schemas import LlmResult


class LlmClientError(RuntimeError):
    pass


# API 키 검증
def validate_api_key(api_key: str = OPENAI_API_KEY) -> None:
    if not api_key.strip():
        raise LlmClientError(
            "OPENAI_API_KEY가 설정되지 않았습니다. "
            "기존 .env 파일에 API 키를 직접 추가해주세요."
        )


# Responses API 호출
def generate_answer(
    developer_prompt: str,
    user_prompt: str,
    api_key: str = OPENAI_API_KEY,
    model: str = OPENAI_MODEL,
    max_output_tokens: int = OPENAI_MAX_OUTPUT_TOKENS,
    timeout_seconds: float = OPENAI_TIMEOUT_SECONDS,
    max_retries: int = OPENAI_MAX_RETRIES,
) -> LlmResult:
    validate_api_key(api_key)
    if max_output_tokens <= 0:
        raise LlmClientError("OPENAI_MAX_OUTPUT_TOKENS는 1 이상이어야 합니다.")
    if timeout_seconds <= 0:
        raise LlmClientError("OPENAI_TIMEOUT_SECONDS는 0보다 커야 합니다.")
    if max_retries < 0:
        raise LlmClientError("OPENAI_MAX_RETRIES는 0 이상이어야 합니다.")

    try:
        import openai
        from openai import OpenAI
    except ImportError as error:
        raise LlmClientError(
            "openai 패키지가 설치되지 않았습니다. "
            "requirements-rag.txt를 설치해주세요."
        ) from error

    client = OpenAI(
        api_key=api_key,
        timeout=timeout_seconds,
        max_retries=max_retries,
    )

    try:
        response = client.responses.create(
            model=model,
            instructions=developer_prompt,
            input=user_prompt,
            max_output_tokens=max_output_tokens,
        )
    except openai.AuthenticationError as error:
        raise LlmClientError(
            "OpenAI API 인증에 실패했습니다. API 키를 확인해주세요."
        ) from error
    except openai.PermissionDeniedError as error:
        raise LlmClientError(
            "OpenAI 모델 또는 프로젝트에 접근할 권한이 없습니다."
        ) from error
    except openai.NotFoundError as error:
        raise LlmClientError(
            "설정된 OpenAI 모델을 사용할 수 없습니다. "
            "OPENAI_MODEL 값을 확인해주세요."
        ) from error
    except openai.RateLimitError as error:
        raise LlmClientError(
            "OpenAI API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
        ) from error
    except openai.APITimeoutError as error:
        raise LlmClientError(
            "OpenAI API 응답 시간이 초과되었습니다."
        ) from error
    except openai.APIConnectionError as error:
        raise LlmClientError(
            "OpenAI API 서버에 연결할 수 없습니다. 네트워크를 확인해주세요."
        ) from error
    except openai.BadRequestError as error:
        raise LlmClientError(
            "OpenAI API 요청 형식이 올바르지 않습니다."
        ) from error
    except openai.InternalServerError as error:
        raise LlmClientError(
            "OpenAI API 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        ) from error
    except openai.APIStatusError as error:
        raise LlmClientError(
            f"OpenAI API 요청에 실패했습니다: HTTP {error.status_code}"
        ) from error
    except openai.APIError as error:
        raise LlmClientError(
            "OpenAI API 처리 중 오류가 발생했습니다."
        ) from error

    answer = str(response.output_text or "").strip()
    if not answer:
        raise LlmClientError("OpenAI API가 비어 있는 응답을 반환했습니다.")

    usage = getattr(response, "usage", None)
    return LlmResult(
        answer=answer,
        model=str(getattr(response, "model", None) or model),
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
        request_id=getattr(response, "_request_id", None),
    )
