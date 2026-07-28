from functools import lru_cache

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import get_settings


@lru_cache
def get_vectorstore(collection_name: str) -> Chroma:
    settings = get_settings()
    embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )
