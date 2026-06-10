from collections.abc import Sequence
from typing import Any

from app.core.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_NORMALIZE,
)


# 임베딩 모델 로딩
def load_embedding_model(
    model_name: str = EMBEDDING_MODEL_NAME,
) -> Any:
    print(
        f"임베딩 모델을 불러옵니다: {model_name}\n"
        "첫 실행은 모델 다운로드로 오래 걸릴 수 있습니다"
    )

    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError(
            "sentence-transformers와 torch가 필요합니다. "
            "requirements-rag.txt를 설치해주세요"
        ) from error

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"임베딩 실행 장치: {device}")
    return SentenceTransformer(model_name, device=device)


# 임베딩 차원 확인
def get_embedding_dimension(model: Any) -> int:
    dimension = model.get_embedding_dimension()
    if dimension is None or int(dimension) <= 0:
        raise ValueError("임베딩 차원을 확인할 수 없습니다")
    return int(dimension)


# 텍스트 임베딩
def embed_texts(
    model: Any,
    texts: Sequence[str],
    batch_size: int = EMBEDDING_BATCH_SIZE,
    normalize_embeddings: bool = EMBEDDING_NORMALIZE,
) -> list[list[float]]:
    valid_texts = [text.strip() for text in texts if text and text.strip()]
    if not valid_texts:
        return []

    embeddings = model.encode(
        valid_texts,
        batch_size=batch_size,
        show_progress_bar=len(valid_texts) > batch_size,
        convert_to_numpy=True,
        normalize_embeddings=normalize_embeddings,
    )
    return [embedding.astype(float).tolist() for embedding in embeddings]
