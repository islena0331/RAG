import json
from pathlib import Path

from app.core.config import OUTPUT_DIR
from app.core.schemas import DocumentMetadata, RagChunk, dataclass_to_dict


# 청크 직렬화
def _serialize_chunk(chunk: RagChunk) -> dict[str, object]:
    return dataclass_to_dict(chunk)


def save_to_json(
    document: DocumentMetadata,
    chunks: list[RagChunk],
    output_dir: str | Path = OUTPUT_DIR,
) -> tuple[Path, Path]:
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)

    document_path = directory / f"{document.document_id}_document.json"
    chunks_path = directory / f"{document.document_id}_chunks.json"

    document_path.write_text(
        json.dumps(dataclass_to_dict(document), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    chunks_path.write_text(
        json.dumps(
            [_serialize_chunk(chunk) for chunk in chunks],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return document_path, chunks_path
