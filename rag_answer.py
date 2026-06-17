import argparse
import re
import sys
from time import perf_counter

from app.core.config import (
    RAG_FALLBACK_SCORE_THRESHOLD,
    RAG_SCORE_THRESHOLD,
    RAG_TOP_K,
)
from app.core.security_policy import (
    get_allowed_document_levels,
    validate_security_level,
)
from app.services.guardrails import (
    check_input_guardrail,
    check_output_guardrail,
)
from app.services.llm_client import LlmClientError, generate_answer
from app.services.prompt_builder import (
    build_general_prompt_bundle,
    build_prompt_bundle,
)
from app.services.question_router import should_skip_retrieval
from app.services.rag_presenter import (
    print_answer,
    print_dry_run,
    print_retrieved_chunks,
)
from app.services.rag_run_logger import record_rag_run
from app.services.retriever import Retriever


# Windows 출력 인코딩 설정
def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


# 사용자 보안등급 입력
def parse_user_security_level(value: str) -> int:
    try:
        level = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "사용자 보안등급은 1, 2, 3 중 하나여야 합니다."
        ) from error

    try:
        return validate_security_level(level)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


# CLI 인자 구성
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Qdrant 검색과 OpenAI Responses API를 사용하는 RAG 질의응답"
    )
    parser.add_argument("--query", required=True, help="질문")
    parser.add_argument(
        "--user-security-level",
        required=True,
        type=parse_user_security_level,
        help="사용자 보안등급 1, 2, 3",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=RAG_TOP_K,
        help=f"최종 검색 결과 수 기본값: {RAG_TOP_K}",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=RAG_SCORE_THRESHOLD,
        help="최소 cosine similarity score",
    )
    parser.add_argument(
        "--include-noisy",
        action="store_true",
        help="noisy chunk 포함",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="검색된 chunk_text 전체 출력",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="OpenAI API 호출 없이 검색 결과와 prompt 출력",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="토큰 예산과 제외 source 정보 출력",
    )
    parser.add_argument(
        "--guard-on",
        action="store_true",
        help="guardrail 연결점 실행",
    )
    return parser


# RAG 실행
def run(args: argparse.Namespace) -> int:
    started_at = perf_counter()
    query = re.sub(r"\s+", " ", args.query).strip()
    if not query:
        raise ValueError("질문을 입력해주세요.")
    # 실제 서비스에서는 로그인 사용자 등급을 서버에서 조회
    user_security_level = validate_security_level(args.user_security_level)
    allowed_levels = get_allowed_document_levels(user_security_level)

    if args.guard_on:
        input_guard = check_input_guardrail(query)
        if not input_guard.allowed:
            record_rag_run(
                status="input_guard_blocked",
                user_security_level=user_security_level,
                allowed_document_levels=allowed_levels,
                dry_run=args.dry_run,
                guard_on=True,
            )
            print(input_guard.reason or "입력 guardrail에서 차단되었습니다.")
            return 0

    sources = []
    answer_mode = "general"
    top_score: float | None = None
    skip_retrieval = should_skip_retrieval(query)

    if not skip_retrieval:
        retriever = Retriever()
        try:
            sources = retriever.retrieve(
                query=query,
                top_k=args.top_k,
                user_security_level=user_security_level,
                score_threshold=args.score_threshold,
                include_noisy=args.include_noisy,
            )
        except ValueError as error:
            if "Qdrant collection이 없습니다" not in str(error):
                raise
            sources = []

    if sources:
        top_score = max(source.score for source in sources)
        answer_mode = "rag"
    if sources and top_score is not None and top_score < RAG_FALLBACK_SCORE_THRESHOLD:
        sources = []
        answer_mode = "general"

    if sources:
        bundle = build_prompt_bundle(
            query=query,
            sources=sources,
            user_security_level=user_security_level,
        )
    else:
        bundle = build_general_prompt_bundle(query=query)

    if args.dry_run:
        log_path = record_rag_run(
            status="dry_run",
            user_security_level=user_security_level,
            allowed_document_levels=allowed_levels,
            sources=bundle.sources,
            dry_run=args.dry_run,
            guard_on=args.guard_on,
            answer_mode=answer_mode,
            top_score=top_score,
            elapsed_ms=(perf_counter() - started_at) * 1000,
        )
        print_dry_run(
            query=query,
            bundle=bundle,
            user_security_level=user_security_level,
            allowed_levels=allowed_levels,
            top_k=args.top_k,
            score_threshold=args.score_threshold,
            show_context=args.show_context,
            guard_on=args.guard_on,
            debug=args.debug,
            log_path=log_path,
        )
        return 0

    if args.show_context and bundle.sources:
        print("[검색 context]")
        print_retrieved_chunks(bundle.sources, True, args.debug)

    result = generate_answer(
        developer_prompt=bundle.developer_prompt,
        user_prompt=bundle.user_prompt,
    )
    if args.guard_on:
        output_guard = check_output_guardrail(result.answer)
        if not output_guard.allowed:
            record_rag_run(
                status="output_guard_blocked",
                user_security_level=user_security_level,
                allowed_document_levels=allowed_levels,
                sources=bundle.sources,
                guard_on=True,
                llm_result=result,
                answer_mode=answer_mode,
                top_score=top_score,
                elapsed_ms=(perf_counter() - started_at) * 1000,
            )
            print(output_guard.reason or "출력 guardrail에서 차단되었습니다.")
            return 0

    log_path = record_rag_run(
        status="completed" if bundle.sources else "completed_without_sources",
        user_security_level=user_security_level,
        allowed_document_levels=allowed_levels,
        sources=bundle.sources,
        guard_on=args.guard_on,
        llm_result=result,
        answer_mode=answer_mode,
        top_score=top_score,
        elapsed_ms=(perf_counter() - started_at) * 1000,
    )

    unknown_citations = print_answer(
        query=query,
        user_security_level=user_security_level,
        allowed_levels=allowed_levels,
        bundle=bundle,
        result=result,
        debug=args.debug,
        log_path=log_path,
    )
    if unknown_citations:
        print(
            "경고: 답변에 존재하지 않는 source ID가 포함되었습니다: "
            + ", ".join(unknown_citations),
            file=sys.stderr,
        )

    return 0


def main() -> int:
    configure_console_encoding()
    args = build_parser().parse_args()
    try:
        return run(args)
    except ConnectionError as error:
        print(
            "오류: 벡터 DB에 연결할 수 없습니다. "
            "`docker compose up -d qdrant` 실행 후 다시 시도해주세요. "
            f"상세: {error}",
            file=sys.stderr,
        )
        return 1
    except (LlmClientError, PermissionError, RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n사용자 요청으로 작업을 중단했습니다.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
