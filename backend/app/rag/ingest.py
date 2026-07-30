"""8절 '문서수집 -> 전처리 -> Vector DB 저장' 파이프라인.

실행:
    cd backend
    python -m app.rag.ingest
"""

from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.vectorstore import get_vectorstore

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[3] / "data" / "knowledge_base"
COLLECTION_NAME = "knowledge_base"


def load_documents() -> list[Document]:
    documents = []
    for path in KNOWLEDGE_BASE_DIR.glob("**/*.md"):
        text = path.read_text(encoding="utf-8")
        documents.append(
            Document(page_content=text, metadata={"source": path.stem})
        )
    return documents


def ingest() -> int:
    documents = load_documents()
    if not documents:
        print(f"'{KNOWLEDGE_BASE_DIR}'에 .md 문서가 없습니다.")
        return 0

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documents)

    vectorstore = get_vectorstore(COLLECTION_NAME)
    vectorstore.add_documents(chunks)

    print(f"{len(documents)}개 문서 -> {len(chunks)}개 청크 적재 완료.")
    return len(chunks)


if __name__ == "__main__":
    ingest()
