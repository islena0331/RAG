from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        print(f"경고: {name} 값이 정수가 아니므로 기본값 {default}을 사용합니다.")
        return default


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False

    print(f"경고: {name} 값이 boolean이 아니므로 기본값 {default}을 사용합니다.")
    return default


def _read_path(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@dataclass(frozen=True)
class Settings:
    mongodb_url: str
    mongodb_db_name: str
    docs_dir: Path
    output_dir: Path
    poppler_path: Path
    tesseract_cmd: Path
    chunk_size: int
    chunk_overlap: int
    min_chunk_length: int
    qdrant_url: str
    qdrant_collection_name: str
    embedding_model_name: str
    embedding_batch_size: int
    embedding_normalize: bool
    embed_skip_noisy: bool
    embed_skip_title: bool


SETTINGS = Settings(
    mongodb_url=os.getenv("MONGODB_URL", "mongodb://localhost:27018"),
    mongodb_db_name=os.getenv("MONGODB_DB_NAME", "rag_prototype"),
    docs_dir=_read_path("DOCS_DIR", "docs"),
    output_dir=_read_path("OUTPUT_DIR", "outputs"),
    poppler_path=_read_path("POPPLER_PATH", r"C:\poppler-26.02.0\Library\bin"),
    tesseract_cmd=_read_path(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ),
    chunk_size=_read_int("CHUNK_SIZE", 1200),
    chunk_overlap=_read_int("CHUNK_OVERLAP", 200),
    min_chunk_length=_read_int("MIN_CHUNK_LENGTH", 50),
    qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    qdrant_collection_name=os.getenv(
        "QDRANT_COLLECTION_NAME",
        "rag_chunks_bge_m3",
    ),
    embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3"),
    embedding_batch_size=_read_int("EMBEDDING_BATCH_SIZE", 4),
    embedding_normalize=_read_bool("EMBEDDING_NORMALIZE", True),
    embed_skip_noisy=_read_bool("EMBED_SKIP_NOISY", True),
    embed_skip_title=_read_bool("EMBED_SKIP_TITLE", True),
)

MONGODB_URL = SETTINGS.mongodb_url
MONGODB_DB_NAME = SETTINGS.mongodb_db_name
DOCS_DIR = SETTINGS.docs_dir
OUTPUT_DIR = SETTINGS.output_dir
POPPLER_PATH = SETTINGS.poppler_path
TESSERACT_CMD = SETTINGS.tesseract_cmd
CHUNK_SIZE = SETTINGS.chunk_size
CHUNK_OVERLAP = SETTINGS.chunk_overlap
MIN_CHUNK_LENGTH = SETTINGS.min_chunk_length
QDRANT_URL = SETTINGS.qdrant_url
QDRANT_COLLECTION_NAME = SETTINGS.qdrant_collection_name
EMBEDDING_MODEL_NAME = SETTINGS.embedding_model_name
EMBEDDING_BATCH_SIZE = SETTINGS.embedding_batch_size
EMBEDDING_NORMALIZE = SETTINGS.embedding_normalize
EMBED_SKIP_NOISY = SETTINGS.embed_skip_noisy
EMBED_SKIP_TITLE = SETTINGS.embed_skip_title
