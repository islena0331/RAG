from pathlib import Path
from typing import TypedDict


DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024


class ValidatedFile(TypedDict):
    filename: str
    path: Path
    size: int
    mime_type: str


def validate_pdf_file(
    file_path: str | Path,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> ValidatedFile:
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise ValueError(f"PDF 파일을 찾을 수 없습니다: {path}")
    if not path.is_file():
        raise ValueError(f"입력 경로가 파일이 아닙니다: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"PDF 파일만 처리할 수 있습니다: {path.name}")

    file_size = path.stat().st_size
    if file_size <= 0:
        raise ValueError(f"파일 크기가 0바이트입니다: {path.name}")
    if file_size > max_file_size:
        max_size_mb = max_file_size / (1024 * 1024)
        raise ValueError(
            f"파일 크기가 제한({max_size_mb:.0f}MB)을 초과했습니다: "
            f"{file_size / (1024 * 1024):.1f}MB"
        )

    return {
        "filename": path.name,
        "path": path,
        "size": file_size,
        "mime_type": "application/pdf",
    }
