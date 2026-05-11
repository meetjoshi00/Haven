from sentence_transformers import SentenceTransformer

from apps.api.config import EMBEDDING_MODEL_NAME

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(text).tolist()


def build_topic_text(meta: dict) -> str:
    parts = [
        meta.get("title", ""),
        meta.get("domain", ""),
        " ".join(meta.get("skills_primary", [])),
        " ".join(meta.get("tags", [])),
    ]
    return " ".join(p for p in parts if p)
