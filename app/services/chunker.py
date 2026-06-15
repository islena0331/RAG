"""청킹 공개 API.

세부 구현은 app.services.chunking 패키지로 분리하고 기존 import 경로는 유지한다.
"""

from app.services.chunking.models import ChunkingResult, SkippedPage
from app.services.chunking.pipeline import create_chunks, create_chunks_with_report
from app.services.chunking.quality import is_noisy_text
from app.services.chunking.splitter import split_text

# 청킹 모듈 공개
__all__ = [
    "ChunkingResult",
    "SkippedPage",
    "create_chunks",
    "create_chunks_with_report",
    "is_noisy_text",
    "split_text",
]
