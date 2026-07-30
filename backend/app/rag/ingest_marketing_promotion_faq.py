"""data/knowledge_base/generated_marketing_promotion_dataset.json(마케팅팀 담당 이벤트/쿠폰
FAQ, 이벤트·쿠폰·할인·프로모션·광고 키워드 커버)를 Supabase(marketing_promotion_faq, 답변
저장) + Chroma(chroma_merged_faq, 질문만 임베딩)로 적재한다. 마케팅_프로모션_분류 규칙
(rules.yaml)의 data_source 공백을 메운다.

질문/답변 모두 원본 그대로 쓴다. LLM 가공 없음. JSON에 이미 있는 id 필드를 그대로
고유 식별자(source_id)로 쓴다.

별도 스테이징 Chroma 컬렉션을 거치지 않고 chroma_merged_faq에 바로 추가한다 —
merge_chroma_faq.py로 전체를 다시 병합하면 이미 들어있는 기존 문서와 중복이 생기기
때문에(문서 ID가 매번 새로 발급됨), 이 스크립트가 새로 추가되는 문서만 직접 넣는다.

실행:
    cd backend
    python -m app.rag.ingest_marketing_promotion_faq load-supabase
    python -m app.rag.ingest_marketing_promotion_faq load-supabase --dry-run
    python -m app.rag.ingest_marketing_promotion_faq load-chroma
    python -m app.rag.ingest_marketing_promotion_faq test
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
    / "generated_marketing_promotion_dataset.json"
)

MERGED_FAQ_COLLECTION_NAME = "chroma_merged_faq"
TABLE_NAME = "marketing_promotion_faq"

# 이 데이터가 어느 데이터셋에서 왔는지 Supabase에 함께 남기기 위한 출처 식별자.
DATASET_SOURCE = "생성된 마케팅/프로모션 FAQ"


def load_records() -> list[dict]:
    return json.loads(INPUT_PATH.read_text(encoding="utf-8"))


def ensure_table(cur) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            source_id INT NOT NULL UNIQUE,
            category TEXT,
            matched_keywords TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            source TEXT NOT NULL,
            department TEXT
        )
        """
    )


def upsert_faq(cur, record: dict) -> int:
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAME}
            (source_id, category, matched_keywords, question, answer, source, department)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id)
        DO UPDATE SET
            category = EXCLUDED.category,
            matched_keywords = EXCLUDED.matched_keywords,
            question = EXCLUDED.question,
            answer = EXCLUDED.answer,
            source = EXCLUDED.source,
            department = EXCLUDED.department
        RETURNING id
        """,
        (
            record["id"],
            record.get("category"),
            ", ".join(record.get("matched_keywords") or []),
            record["문의"],
            record["답변"],
            DATASET_SOURCE,
            record.get("담당부서"),
        ),
    )
    return cur.fetchone()[0]


def ingest_supabase(dry_run: bool = False) -> int:
    """generated_marketing_promotion_dataset.json을 읽어 Supabase(marketing_promotion_faq)에만 저장한다."""
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


def fetch_id(cur, source_id: int) -> int | None:
    cur.execute(f"SELECT id FROM {TABLE_NAME} WHERE source_id = %s", (source_id,))
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
                supabase_id = fetch_id(cur, record["id"])
                if supabase_id is None:
                    print(f"경고: Supabase에 없는 FAQ라 건너뜀 - source_id={record['id']}")
                    continue
                documents.append(
                    Document(
                        page_content=record["문의"],
                        metadata={
                            "supabase_id": supabase_id,
                            "source_table": TABLE_NAME,
                            "category": record.get("category") or "",
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
    """테스트: '쿠폰 유효기간이 언제까지인가요' 질문으로 검색해 결과를 출력한다."""
    query = "쿠폰 유효기간이 언제까지인가요"
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
