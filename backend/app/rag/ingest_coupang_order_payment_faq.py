"""data/knowledge_base/coupang_faq_order_payment.json(쿠팡 주문/결제 FAQ, PDF 9편
ep_1~ep_9)을 Supabase(coupang_faq_order_payment, 답변 저장) + Chroma(chroma_merged_faq,
질문만 임베딩)로 적재한다. 환불/취소가 아닌 주문 절차·장바구니·결제수단·쿠페이·고객확인
제도 안내 문의라 "안내/조회"·"일반문의" 문의유형의 담당부서인 고객센터의 RAG 근거로
쓰인다.

질문/답변 모두 원본 그대로 쓴다. LLM 가공 없음.

별도 스테이징 Chroma 컬렉션을 거치지 않고 chroma_merged_faq에 바로 추가한다 —
merge_chroma_faq.py로 전체를 다시 병합하면 이미 들어있는 기존 문서와 중복이 생기기
때문에(문서 ID가 매번 새로 발급됨), 이 스크립트가 새로 추가되는 문서만 직접 넣는다.

실행:
    cd backend
    python -m app.rag.ingest_coupang_order_payment_faq load-supabase
    python -m app.rag.ingest_coupang_order_payment_faq load-supabase --dry-run
    python -m app.rag.ingest_coupang_order_payment_faq load-chroma
    python -m app.rag.ingest_coupang_order_payment_faq test
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_BACKEND_DIR = str(Path(__file__).resolve().parents[2])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import psycopg2
from langchain_core.documents import Document

from app.core.config import get_settings
from app.rag.vectorstore import get_vectorstore

INPUT_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "knowledge_base"
    / "coupang_faq_order_payment.json"
)

MERGED_FAQ_COLLECTION_NAME = "chroma_merged_faq"
TABLE_NAME = "coupang_faq_order_payment"

# 이 데이터가 어느 데이터셋에서 왔는지 Supabase에 함께 남기기 위한 출처 식별자.
DATASET_SOURCE = "공식 쿠팡 정책"


def load_records() -> list[dict]:
    return json.loads(INPUT_PATH.read_text(encoding="utf-8"))


def ensure_table(cur) -> None:
    # source_url은 이 데이터셋엔 없지만(전부 PDF 출처), retrieve_node._fetch_faq_row가
    # _PDF_STYLE_TABLES 전체에 공유하는 조회 쿼리가 이 컬럼을 항상 SELECT하므로 맞춰준다.
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            source TEXT NOT NULL,
            source_url TEXT,
            source_pdf_file TEXT,
            source_pdf_question_number INT,
            UNIQUE (source_pdf_file, source_pdf_question_number)
        )
        """
    )


def upsert_faq(cur, record: dict) -> int:
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAME}
            (question, answer, source, source_url, source_pdf_file, source_pdf_question_number)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_pdf_file, source_pdf_question_number)
        DO UPDATE SET
            question = EXCLUDED.question,
            answer = EXCLUDED.answer,
            source = EXCLUDED.source
        RETURNING id
        """,
        (
            record["question"],
            record["answer"],
            DATASET_SOURCE,
            None,
            record["source_file"],
            record["question_number"],
        ),
    )
    return cur.fetchone()[0]


def ingest_supabase(dry_run: bool = False) -> int:
    """coupang_faq_order_payment.json을 읽어 Supabase(coupang_faq_order_payment)에만 저장한다."""
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

    print(f"{len(records)}건을 Supabase({TABLE_NAME})에 적재했습니다.")
    return len(records)


def fetch_id(cur, source_pdf_file: str, source_pdf_question_number: int) -> int | None:
    cur.execute(
        f"SELECT id FROM {TABLE_NAME} WHERE source_pdf_file = %s AND source_pdf_question_number = %s",
        (source_pdf_file, source_pdf_question_number),
    )
    row = cur.fetchone()
    return row[0] if row else None


def ingest_chroma(dry_run: bool = False) -> int:
    """Supabase에 이미 적재된 레코드의 id를 다시 조회해, 질문만 임베딩해
    chroma_merged_faq에 직접 추가한다(별도 스테이징 컬렉션을 거치지 않음)."""
    records = load_records()
    print(f"{len(records)}건의 FAQ를 불러왔습니다.")

    if dry_run:
        records = records[:5]
        print(f"--dry-run: {len(records)}건만 적재합니다.")

    settings = get_settings()
    vectorstore = get_vectorstore(MERGED_FAQ_COLLECTION_NAME)

    documents = []
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn, conn.cursor() as cur:
            for record in records:
                supabase_id = fetch_id(cur, record["source_file"], record["question_number"])
                if supabase_id is None:
                    print(f"경고: Supabase에 없는 FAQ라 건너뜀 - {record['source_file']}#{record['question_number']}")
                    continue
                documents.append(
                    Document(
                        page_content=record["question"],
                        metadata={
                            "supabase_id": supabase_id,
                            "source_table": TABLE_NAME,
                        },
                    )
                )
    finally:
        conn.close()

    if documents:
        vectorstore.add_documents(documents)

    print(f"{len(documents)}건을 Chroma('{MERGED_FAQ_COLLECTION_NAME}')에 추가했습니다.")
    return len(documents)


def test_search() -> None:
    """테스트: '결제수단에는 어떤 것들이 있나요' 질문으로 검색해 결과를 출력한다."""
    query = "결제수단에는 어떤 것들이 있나요"
    vectorstore = get_vectorstore(MERGED_FAQ_COLLECTION_NAME)
    results = vectorstore.similarity_search_with_relevance_scores(query, k=3)

    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            for doc, score in results:
                source_table = doc.metadata.get("source_table")
                supabase_id = doc.metadata.get("supabase_id")
                print(f"[{source_table}:{supabase_id}] score={score:.3f} 질문={doc.page_content}")
                if source_table == TABLE_NAME:
                    cur.execute(f"SELECT answer FROM {TABLE_NAME} WHERE id = %s", (supabase_id,))
                    row = cur.fetchone()
                    print(f"  답변: {(row[0] if row else '(없음)')[:80]}...")
    finally:
        conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    command = args[0] if args and not args[0].startswith("--") else "load-supabase"
    dry_run = "--dry-run" in args

    if command == "load-supabase":
        ingest_supabase(dry_run=dry_run)
    elif command == "load-chroma":
        ingest_chroma(dry_run=dry_run)
    elif command == "test":
        test_search()
    else:
        raise SystemExit(f"알 수 없는 명령: {command}")
