"""build_coupang_faq.py가 만든 data/knowledge_base/coupang_faq_combined.json을
Supabase(답변 저장) + Chroma(질문만 임베딩) 구조로 RAG에 적재한다.

질문/답변 모두 원본 그대로 쓴다. LLM 가공 없음.

실행:
    cd backend
    python -m app.rag.ingest_coupang_faq load-supabase        # Supabase(coupang_faq)에만 적재
    python -m app.rag.ingest_coupang_faq load-supabase --dry-run
    python -m app.rag.ingest_coupang_faq load-chroma          # 질문만 임베딩 (Supabase에 먼저 있어야 함)
    python -m app.rag.ingest_coupang_faq test                  # '반품하면 언제 환불되나요'로 검색 테스트
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# IDE의 "실행" 버튼처럼 이 파일을 모듈(-m)이 아니라 직접 파일 경로로 실행하는 경우,
# backend/가 sys.path에 없어서 `app.*` 임포트가 실패한다. 그런 경우를 대비해 보정한다.
_BACKEND_DIR = str(Path(__file__).resolve().parents[2])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import psycopg2
from langchain_core.documents import Document
from tqdm import tqdm

from app.core.config import get_settings
from app.rag.vectorstore import get_vectorstore

INPUT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "knowledge_base" / "coupang_faq_combined.json"
)

CHROMA_COLLECTION_NAME = "chroma_coupang_faq"

# 이 데이터가 어느 데이터셋에서 왔는지 Supabase에 함께 남기기 위한 출처 식별자.
DATASET_SOURCE = "공식 쿠팡 정책"


def load_records() -> list[dict]:
    return json.loads(INPUT_PATH.read_text(encoding="utf-8"))


def ensure_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS coupang_faq (
            id SERIAL PRIMARY KEY,
            faq_id INT NOT NULL UNIQUE,
            category TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            source TEXT NOT NULL,
            source_url TEXT,
            published_date TEXT,
            source_pdf_file TEXT,
            source_pdf_question_number INT,
            source_pdf_note TEXT
        )
        """
    )
    # 이미 배포된 테이블에는 CREATE TABLE IF NOT EXISTS가 컬럼을 추가해주지 않으므로 별도 보정.
    cur.execute("ALTER TABLE coupang_faq ADD COLUMN IF NOT EXISTS source_pdf_file TEXT")
    cur.execute("ALTER TABLE coupang_faq ADD COLUMN IF NOT EXISTS source_pdf_question_number INT")
    cur.execute("ALTER TABLE coupang_faq ADD COLUMN IF NOT EXISTS source_pdf_note TEXT")


def upsert_faq(cur, record: dict) -> int:
    cur.execute(
        """
        INSERT INTO coupang_faq
            (faq_id, category, question, answer, source, source_url, published_date,
             source_pdf_file, source_pdf_question_number, source_pdf_note)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (faq_id)
        DO UPDATE SET
            category = EXCLUDED.category,
            question = EXCLUDED.question,
            answer = EXCLUDED.answer,
            source = EXCLUDED.source,
            source_url = EXCLUDED.source_url,
            published_date = EXCLUDED.published_date,
            source_pdf_file = EXCLUDED.source_pdf_file,
            source_pdf_question_number = EXCLUDED.source_pdf_question_number,
            source_pdf_note = EXCLUDED.source_pdf_note
        RETURNING id
        """,
        (
            record["id"],
            record.get("category"),
            record["question"],
            record["answer"],
            DATASET_SOURCE,
            record.get("source_url"),
            record.get("published_date"),
            record.get("source_pdf_file"),
            record.get("source_pdf_question_number"),
            record.get("source_pdf_note"),
        ),
    )
    return cur.fetchone()[0]


def ingest_supabase(dry_run: bool = False) -> int:
    """coupang_faq_combined.json을 읽어 Supabase(coupang_faq)에만 저장한다. Chroma는 건드리지 않는다."""
    records = load_records()
    print(f"{len(records)}건의 FAQ를 불러왔습니다.")

    if dry_run:
        records = records[:5]
        print(f"--dry-run: {len(records)}건만 적재합니다.")

    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn, conn.cursor() as cur:
            ensure_table(cur)
            for record in records:
                upsert_faq(cur, record)
    finally:
        conn.close()

    print(f"{len(records)}건을 Supabase(coupang_faq)에 적재했습니다.")
    return len(records)


def fetch_faq_id(cur, faq_id: int) -> int | None:
    cur.execute("SELECT id FROM coupang_faq WHERE faq_id = %s", (faq_id,))
    row = cur.fetchone()
    return row[0] if row else None


def ingest_chroma(dry_run: bool = False) -> int:
    """Supabase에 이미 적재된 faq_id로 id를 다시 조회해, 질문만 임베딩해
    Chroma(chroma_coupang_faq)에 저장한다."""
    records = load_records()
    print(f"{len(records)}건의 FAQ를 불러왔습니다.")

    if dry_run:
        records = records[:5]
        print(f"--dry-run: {len(records)}건만 적재합니다.")

    settings = get_settings()
    vectorstore = get_vectorstore(CHROMA_COLLECTION_NAME)

    documents = []
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn, conn.cursor() as cur:
            for record in tqdm(records, desc="Supabase 조회"):
                faq_id = record["id"]
                supabase_id = fetch_faq_id(cur, faq_id)
                if supabase_id is None:
                    tqdm.write(f"경고: Supabase에 없는 FAQ라 건너뜀 - faq_id={faq_id}")
                    continue
                documents.append(
                    Document(
                        page_content=record["question"],
                        metadata={
                            "supabase_id": supabase_id,
                            "faq_id": faq_id,
                            "category": record.get("category") or "",
                        },
                    )
                )
    finally:
        conn.close()

    batch_size = 50
    batches = [documents[start : start + batch_size] for start in range(0, len(documents), batch_size)]
    for batch in tqdm(batches, desc="Chroma 임베딩", unit="batch"):
        vectorstore.add_documents(batch)

    print(f"{len(documents)}건을 Chroma('{CHROMA_COLLECTION_NAME}')에 적재했습니다.")
    return len(documents)


def search_answer(query: str, k: int = 1) -> list[dict]:
    """Chroma(chroma_coupang_faq)에서 query와 가장 유사한 질문을 찾고,
    metadata.supabase_id로 Supabase(coupang_faq)에서 실제 답변을 조회한다."""
    vectorstore = get_vectorstore(CHROMA_COLLECTION_NAME)
    results = vectorstore.similarity_search_with_relevance_scores(query, k=k)

    settings = get_settings()
    matches = []
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            for doc, score in results:
                supabase_id = doc.metadata.get("supabase_id")
                cur.execute("SELECT answer FROM coupang_faq WHERE id = %s", (supabase_id,))
                row = cur.fetchone()
                matches.append(
                    {
                        "score": score,
                        "question": doc.page_content,
                        "supabase_id": supabase_id,
                        "answer": row[0] if row else None,
                    }
                )
    finally:
        conn.close()

    return matches


def test_search_refund() -> None:
    """테스트: '반품하면 언제 환불되나요' 질문으로 검색해 결과를 출력한다."""
    query = "반품하면 언제 환불되나요"
    matches = search_answer(query, k=1)

    if not matches:
        print("검색 결과가 없습니다.")
        return

    best = matches[0]
    print(f"질문: {query}")
    print(f"유사도(score): {best['score']}")
    print(f"가장 유사한 page_content: {best['question']}")
    print()
    print(f"Supabase 답변(id={best['supabase_id']}):")
    print(best["answer"])


if __name__ == "__main__":
    args = sys.argv[1:]
    command = args[0] if args and not args[0].startswith("--") else "load-supabase"
    dry_run = "--dry-run" in args

    ingest_supabase(dry_run=dry_run)
    ingest_chroma(dry_run=dry_run)
    test_search_refund()
