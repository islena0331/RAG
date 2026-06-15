import json
from pathlib import Path
import re

from app.core.config import (
    EMBEDDING_MODEL_NAME,
    OPENAI_MAX_OUTPUT_TOKENS,
    QDRANT_COLLECTION_NAME,
    RAG_MAX_CHUNKS_PER_DOCUMENT,
    RAG_MAX_CONTEXT_TOKENS,
    RAG_MAX_INPUT_TOKENS,
)
from app.core.schemas import LlmResult, PromptBundle, RetrievedChunk


# 페이지 표시
def format_pages(page_numbers: list[int]) -> str:
    if not page_numbers:
        return "페이지 정보 없음"
    return ", ".join(str(page) for page in page_numbers) + "페이지"


# 검색 결과 출력
def print_retrieved_chunks(
    sources: list[RetrievedChunk],
    show_context: bool,
    debug: bool = False,
) -> None:
    for index, source in enumerate(sources, start=1):
        text = source.chunk_text if show_context else source.chunk_text[:300]
        if not show_context and len(source.chunk_text) > 300:
            text += "..."

        print(f"\n[검색 결과 {index}]")
        print(f"source_id: {source.source_id}")
        print(f"document_title: {source.document_title}")
        print(f"page_numbers: {source.page_numbers}")
        if debug:
            print(f"score: {source.score:.6f}")
            print(f"chunk_id: {source.chunk_id}")
            print(f"document_id: {source.document_id}")
            print(f"security_level: {source.security_level}")
            print("labels: " + json.dumps(source.labels, ensure_ascii=False))
        print(f"chunk_text:\n{text}")


# 출처 목록 출력
def print_sources(sources: list[RetrievedChunk]) -> None:
    print("\n[출처]")
    for source in sources:
        print(
            f"- [{source.source_id}] "
            f"{source.document_title}, {format_pages(source.page_numbers)}"
        )


# citation ID 검증
def find_unknown_citations(
    answer: str,
    sources: list[RetrievedChunk],
) -> list[str]:
    valid_ids = {source.source_id for source in sources}
    cited_ids = set(re.findall(r"\[(S\d+)\]", answer))
    return sorted(cited_ids - valid_ids)


# dry-run 출력
def print_dry_run(
    query: str,
    bundle: PromptBundle,
    user_security_level: int,
    allowed_levels: list[int],
    top_k: int,
    score_threshold: float | None,
    show_context: bool,
    guard_on: bool,
    debug: bool,
    log_path: Path | None,
) -> None:
    print("[RAG 검색 정보]")
    print(f"질문: {query}")
    print(f"임베딩 모델: {EMBEDDING_MODEL_NAME}")
    print(f"Qdrant collection: {QDRANT_COLLECTION_NAME}")
    print(f"top_k: {top_k}")
    print(f"score threshold: {score_threshold}")
    print(f"사용자 보안등급: {user_security_level}급")
    print(
        "접근 가능 문서등급: "
        + ", ".join(f"{level}급" for level in allowed_levels)
    )
    print(f"검색 결과 수: {len(bundle.sources)}")
    print(f"context 토큰 수: {bundle.context_token_count}")
    print(f"전체 예상 입력 토큰 수: {bundle.input_token_count}")

    print_retrieved_chunks(bundle.sources, show_context, debug)
    print("\n[Developer Prompt]")
    print(bundle.developer_prompt)
    print("\n[User Prompt]")
    print(bundle.user_prompt)
    print_sources(bundle.sources)

    if debug:
        print("\n[Debug]")
        print(f"RAG_MAX_INPUT_TOKENS: {RAG_MAX_INPUT_TOKENS}")
        print(f"RAG_MAX_CONTEXT_TOKENS: {RAG_MAX_CONTEXT_TOKENS}")
        print(
            "RAG_MAX_CHUNKS_PER_DOCUMENT: "
            f"{RAG_MAX_CHUNKS_PER_DOCUMENT}"
        )
        print(f"OPENAI_MAX_OUTPUT_TOKENS: {OPENAI_MAX_OUTPUT_TOKENS}")
        print(f"guardrail 연결: {guard_on}")
        print(f"제외 source: {bundle.excluded_sources}")
        print(f"축약 source: {bundle.truncated_sources}")
        if log_path is not None:
            print(f"실행 기록: {log_path}")


# 최종 답변 출력
def print_answer(
    query: str,
    user_security_level: int,
    allowed_levels: list[int],
    bundle: PromptBundle,
    result: LlmResult,
    debug: bool,
    log_path: Path | None,
) -> list[str]:
    print("[RAG 질문]")
    print(query)
    print("\n[RAG 답변]")
    print(result.answer)
    print_sources(bundle.sources)

    print("\n[사용 정보]")
    print(f"모델: {result.model}")
    print(f"검색 chunk 수: {len(bundle.sources)}")
    if result.input_tokens is not None:
        print(f"입력 토큰: {result.input_tokens}")
    if result.output_tokens is not None:
        print(f"출력 토큰: {result.output_tokens}")
    if result.total_tokens is not None:
        print(f"전체 토큰: {result.total_tokens}")
    if debug and result.request_id:
        print(f"request_id: {result.request_id}")
    if debug:
        print(f"사용자 보안등급: {user_security_level}급")
        print(
            "접근 가능 문서등급: "
            + ", ".join(f"{level}급" for level in allowed_levels)
        )
        print(f"제외 source: {bundle.excluded_sources}")
        print(f"축약 source: {bundle.truncated_sources}")
        if log_path is not None:
            print(f"실행 기록: {log_path}")

    return find_unknown_citations(result.answer, bundle.sources)
