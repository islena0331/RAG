from pathlib import Path
from xml.sax.saxutils import escape

from app.core.config import (
    GPT_4O_MINI_CONTEXT_WINDOW,
    GPT_4O_MINI_MAX_OUTPUT_TOKENS,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    PROJECT_ROOT,
    RAG_MAX_CONTEXT_TOKENS,
    RAG_MAX_INPUT_TOKENS,
)
from app.core.security_policy import (
    is_access_allowed,
    validate_security_level,
)
from app.core.schemas import PromptBundle, RetrievedChunk
from app.services.token_budget import (
    count_tokens,
    fit_sources_to_budget,
)


DEVELOPER_PROMPT_PATH = (
    PROJECT_ROOT / "app" / "prompts" / "rag_developer_prompt.txt"
)
MODEL_LIMITS = {
    "gpt-4o-mini": (
        GPT_4O_MINI_CONTEXT_WINDOW,
        GPT_4O_MINI_MAX_OUTPUT_TOKENS,
    )
}


# 페이지 번호 표시
def _format_pages(page_numbers: list[int]) -> str:
    if not page_numbers:
        return "페이지 정보 없음"
    return ", ".join(str(page) for page in page_numbers)


# source XML 생성
def render_source_xml(source: RetrievedChunk) -> str:
    return (
        f'  <document source_id="{escape(source.source_id)}">\n'
        "    <metadata>\n"
        f"      <document_id>{escape(source.document_id)}</document_id>\n"
        f"      <title>{escape(source.document_title)}</title>\n"
        f"      <pages>{escape(_format_pages(source.page_numbers))}</pages>\n"
        "    </metadata>\n"
        "    <document_content>\n"
        f"{escape(source.chunk_text)}\n"
        "    </document_content>\n"
        "  </document>"
    )


# Developer prompt 로딩
def load_developer_prompt(
    prompt_path: Path = DEVELOPER_PROMPT_PATH,
) -> str:
    try:
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(
            f"Developer prompt를 읽을 수 없습니다: {prompt_path}"
        ) from error
    if not prompt:
        raise RuntimeError("Developer prompt가 비어 있습니다.")
    return prompt


# User prompt 생성
def _build_user_prompt(
    query: str,
    sources: list[RetrievedChunk],
) -> tuple[str, str]:
    documents_xml = "\n".join(render_source_xml(source) for source in sources)
    user_prompt = (
        "<retrieved_documents>\n"
        f"{documents_xml}\n"
        "</retrieved_documents>\n\n"
        "<user_question>\n"
        f"{escape(query)}\n"
        "</user_question>"
    )
    return user_prompt, documents_xml


# RAG prompt 묶음 생성
def build_prompt_bundle(
    query: str,
    sources: list[RetrievedChunk],
    user_security_level: int,
    model_name: str = OPENAI_MODEL,
    max_input_tokens: int = RAG_MAX_INPUT_TOKENS,
    max_context_tokens: int = RAG_MAX_CONTEXT_TOKENS,
    max_output_tokens: int = OPENAI_MAX_OUTPUT_TOKENS,
) -> PromptBundle:
    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("질문을 입력해주세요.")
    if not sources:
        raise ValueError("Prompt를 생성할 검색 결과가 없습니다.")
    validated_user_level = validate_security_level(user_security_level)
    if any(
        not is_access_allowed(
            validated_user_level,
            source.security_level,
        )
        for source in sources
    ):
        raise PermissionError(
            "접근 권한 검증에 실패하여 prompt를 생성하지 않습니다."
        )
    if (
        max_input_tokens <= 0
        or max_context_tokens <= 0
        or max_output_tokens <= 0
    ):
        raise ValueError("토큰 예산은 1 이상이어야 합니다.")

    model_limits = MODEL_LIMITS.get(model_name)
    if model_limits is not None:
        _, model_max_output_tokens = model_limits
        if max_output_tokens > model_max_output_tokens:
            raise ValueError(
                f"{model_name}의 최대 출력 토큰은 "
                f"{model_max_output_tokens}입니다."
            )

    developer_prompt = load_developer_prompt()
    empty_user_prompt, _ = _build_user_prompt(normalized_query, [])
    fixed_tokens = count_tokens(
        developer_prompt + "\n" + empty_user_prompt,
        model_name,
    )
    available_context_tokens = min(
        max_context_tokens,
        max_input_tokens - fixed_tokens - 32,
    )
    if available_context_tokens <= 0:
        raise ValueError(
            "Developer prompt와 질문이 RAG_MAX_INPUT_TOKENS를 초과합니다."
        )

    budget_result = fit_sources_to_budget(
        sources=sources,
        max_tokens=available_context_tokens,
        model_name=model_name,
        render_source=render_source_xml,
    )
    selected_sources = list(budget_result.sources)
    excluded_sources = list(budget_result.excluded_sources)
    if not selected_sources:
        raise ValueError("토큰 예산 안에 포함할 수 있는 검색 결과가 없습니다.")
    if any(
        not is_access_allowed(
            validated_user_level,
            source.security_level,
        )
        for source in selected_sources
    ):
        raise PermissionError(
            "접근 권한 검증에 실패하여 prompt를 생성하지 않습니다."
        )

    while selected_sources:
        user_prompt, documents_xml = _build_user_prompt(
            normalized_query,
            selected_sources,
        )
        input_token_count = count_tokens(
            developer_prompt + "\n" + user_prompt,
            model_name,
        )
        if input_token_count <= max_input_tokens:
            break
        removed = selected_sources.pop()
        excluded_sources.insert(0, removed.source_id)
    else:
        raise ValueError("RAG_MAX_INPUT_TOKENS 안에 prompt를 구성할 수 없습니다.")

    context_token_count = count_tokens(documents_xml, model_name)
    if model_limits is not None:
        context_window, _ = model_limits
        if input_token_count + max_output_tokens > context_window:
            raise ValueError(
                f"{model_name} context 한도를 초과합니다: "
                f"입력={input_token_count}, 출력예약={max_output_tokens}, "
                f"한도={context_window}"
            )

    return PromptBundle(
        developer_prompt=developer_prompt,
        user_prompt=user_prompt,
        sources=selected_sources,
        input_token_count=input_token_count,
        context_token_count=context_token_count,
        excluded_sources=excluded_sources,
        truncated_sources=budget_result.truncated_sources,
    )
