from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.core.config import OUTPUT_DIR
from app.core.schemas import LlmResult, RetrievedChunk


RAG_RUN_LOG_PATH = OUTPUT_DIR / "rag_runs.jsonl"


# RAG 실행 결과 기록
def record_rag_run(
    status: str,
    user_security_level: int,
    allowed_document_levels: list[int],
    sources: list[RetrievedChunk] | None = None,
    dry_run: bool = False,
    guard_on: bool = False,
    llm_result: LlmResult | None = None,
    error_type: str | None = None,
    log_path: Path = RAG_RUN_LOG_PATH,
) -> Path | None:
    source_items = sources or []
    record: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "user_security_level": user_security_level,
        "allowed_document_levels": allowed_document_levels,
        "source_count": len(source_items),
        "source_ids": [source.source_id for source in source_items],
        "document_ids": sorted(
            {source.document_id for source in source_items if source.document_id}
        ),
        "dry_run": dry_run,
        "guard_on": guard_on,
        "error_type": error_type,
    }

    if llm_result is not None:
        record.update(
            {
                "model": llm_result.model,
                "input_tokens": llm_result.input_tokens,
                "output_tokens": llm_result.output_tokens,
                "total_tokens": llm_result.total_tokens,
                "request_id": llm_result.request_id,
            }
        )

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return log_path
    except OSError as error:
        print(f"경고: RAG 실행 기록 저장에 실패했습니다: {error}")
        return None
