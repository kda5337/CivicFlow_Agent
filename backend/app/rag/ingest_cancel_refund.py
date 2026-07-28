"""'취소/반품/교환/환불/AS' 상담 데이터(data/ai_hub/cancel_refund_summaries.json)를
Supabase(답변 저장) + Chroma(질문 임베딩) 구조로 RAG에 적재한다.

질문/답변 모두 LLM 가공 없이 만든다 — consulting_content 원문이
"고객: ...\\n상담사: ...\\n고객: ...\\n상담사: ..." 형태로 화자가 표시되어 있어서,
'고객:' 발화만 그대로 이어붙인 걸 질문으로, '상담사:' 발화만 그대로 이어붙인 걸
답변으로 쓴다. (요약 instruction의 output이나 LLM이 생성한 문장은 전혀 쓰지 않는다.)

3단계로 나뉜다:
1. build_qa_pairs(): 세션별로 질문/답변을 추출해 별도 파일에 저장한다. DB에는 쓰지 않는다.
2. ingest_supabase(): 그 파일을 읽어 Supabase의 cancel_refund_faq 테이블에만 저장한다.
   Chroma는 건드리지 않는다.
3. ingest_chroma(): Supabase에서 (source, source_id)로 id를 다시 조회해, 질문 텍스트만
   임베딩해 Chroma에 저장한다(metadata에 supabase_id를 남겨 나중에 답변을 역참조).

실행:
    cd backend
    python -m app.rag.ingest_cancel_refund build              # 질문/답변만 뽑아서 파일로 저장
    python -m app.rag.ingest_cancel_refund build --dry-run     # 5건만 시험
    python -m app.rag.ingest_cancel_refund load-supabase       # Supabase에만 적재
    python -m app.rag.ingest_cancel_refund load-chroma         # Chroma에만 적재 (Supabase에 먼저 있어야 함)
"""
import json
import re
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

from app.core.config import get_settings
from app.rag.vectorstore import get_vectorstore

INPUT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "ai_hub" / "cancel_refund_summaries.json"
)
QA_PAIRS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "ai_hub" / "cancel_refund_qa_pairs.json"
)

# consulting_content는 "고객: ...\n상담사: ...\n고객: ...\n상담사: ..." 형태로
# 화자 표시가 줄 단위로 되어 있다. 회사마다 고객 쪽 라벨이 달라서(액티벤처/엘지유플러스는
# '고객', 하나카드는 '손님') 둘 다 같은 역할로 취급한다. 전체 데이터를 스캔해 확인한
# 라벨은 이 3개뿐이다(상담사/손님/고객).
_TURN_PATTERN = re.compile(r"(?:^|\n)(고객|손님|상담사):\s*")
_CUSTOMER_LABELS = {"고객", "손님"}
_COUNSELOR_LABELS = {"상담사"}


def extract_turns(consulting_content: str, speaker: str) -> str:
    """상담 원문에서 지정한 화자(customer/counselor)의 발화만 그대로 골라 이어붙인다 (가공 없음)."""
    labels = _CUSTOMER_LABELS if speaker == "customer" else _COUNSELOR_LABELS
    parts = _TURN_PATTERN.split(consulting_content)
    turns = []
    for i in range(1, len(parts), 2):
        turn_speaker = parts[i]
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if turn_speaker in labels and text:
            turns.append(text)
    return "\n".join(turns)


def load_sessions() -> list[dict]:
    return json.loads(INPUT_PATH.read_text(encoding="utf-8"))


def build_qa_pairs(dry_run: bool = False) -> list[dict]:
    """세션별 consulting_content에서 고객 발화(질문)/상담사 발화(답변)를 그대로 뽑아 저장한다.
    LLM을 전혀 호출하지 않는다."""
    sessions = load_sessions()
    print(f"{len(sessions)}개 세션을 찾았습니다.")

    if dry_run:
        sessions = sessions[:5]
        print(f"--dry-run: {len(sessions)}건만 처리합니다.")

    qa_pairs = []
    for session in sessions:
        consulting_content = session.get("consulting_content") or ""
        question = extract_turns(consulting_content, "customer")
        answer = extract_turns(consulting_content, "counselor")
        if not question or not answer:
            continue
        qa_pairs.append(
            {
                "source": session.get("source"),
                "source_id": session.get("source_id"),
                "consulting_category": session.get("consulting_category"),
                "question": question,
                "answer": answer,
            }
        )

    QA_PAIRS_PATH.write_text(json.dumps(qa_pairs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(qa_pairs)}건을 {QA_PAIRS_PATH}에 저장했습니다.")
    return qa_pairs


def ensure_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cancel_refund_faq (
            id SERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            source_id TEXT NOT NULL,
            consulting_category TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            UNIQUE (source, source_id)
        )
        """
    )


def upsert_faq(cur, qa_pair: dict) -> int:
    cur.execute(
        """
        INSERT INTO cancel_refund_faq
            (source, source_id, consulting_category, question, answer)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source, source_id)
        DO UPDATE SET question = EXCLUDED.question, answer = EXCLUDED.answer
        RETURNING id
        """,
        (
            qa_pair["source"],
            qa_pair["source_id"],
            qa_pair["consulting_category"],
            qa_pair["question"],
            qa_pair["answer"],
        ),
    )
    return cur.fetchone()[0]


def ingest_supabase(dry_run: bool = False) -> int:
    """build_qa_pairs()가 만든 질문/답변 쌍을 Supabase(cancel_refund_faq)에만 저장한다. Chroma는 건드리지 않는다."""
    qa_pairs = json.loads(QA_PAIRS_PATH.read_text(encoding="utf-8"))
    print(f"{len(qa_pairs)}개의 질문-답변 쌍을 불러왔습니다.")

    if dry_run:
        qa_pairs = qa_pairs[:5]
        print(f"--dry-run: {len(qa_pairs)}건만 적재합니다.")

    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn, conn.cursor() as cur:
            ensure_table(cur)
            for qa_pair in qa_pairs:
                upsert_faq(cur, qa_pair)
    finally:
        conn.close()

    print(f"{len(qa_pairs)}건을 Supabase(cancel_refund_faq)에 적재했습니다.")
    return len(qa_pairs)


def fetch_faq_id(cur, source: str, source_id: str) -> int | None:
    cur.execute(
        "SELECT id FROM cancel_refund_faq WHERE source = %s AND source_id = %s",
        (source, source_id),
    )
    row = cur.fetchone()
    return row[0] if row else None


CHROMA_COLLECTION_NAME = "chroma_cancel_category"


def ingest_chroma(dry_run: bool = False) -> int:
    """Supabase에 이미 적재된 (source, source_id)로 id를 다시 조회해, 질문만 임베딩해 Chroma에 저장한다."""
    qa_pairs = json.loads(QA_PAIRS_PATH.read_text(encoding="utf-8"))
    print(f"{len(qa_pairs)}개의 질문-답변 쌍을 불러왔습니다.")

    if dry_run:
        qa_pairs = qa_pairs[:5]
        print(f"--dry-run: {len(qa_pairs)}건만 적재합니다.")

    settings = get_settings()
    vectorstore = get_vectorstore(CHROMA_COLLECTION_NAME)

    documents = []
    total = len(qa_pairs)
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn, conn.cursor() as cur:
            for i, qa_pair in enumerate(qa_pairs, start=1):
                faq_id = fetch_faq_id(cur, qa_pair["source"], qa_pair["source_id"])
                if faq_id is None:
                    print(f"경고: Supabase에 없는 세션이라 건너뜀 - {qa_pair['source']}/{qa_pair['source_id']}", flush=True)
                    continue
                documents.append(
                    Document(
                        page_content=qa_pair["question"],
                        metadata={
                            "supabase_id": faq_id,
                            "source": qa_pair["source"],
                            "consulting_category": qa_pair["consulting_category"],
                        },
                    )
                )
                if i % 100 == 0 or i == total:
                    print(f"Supabase 조회: {i}/{total}", flush=True)
    finally:
        conn.close()

    batch_size = 50
    embedded = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        vectorstore.add_documents(batch)
        embedded += len(batch)
        print(f"Chroma 임베딩: {embedded}/{len(documents)}", flush=True)

    print(f"{len(documents)}건을 Chroma에 적재했습니다.")
    return len(documents)


def search_answer(query: str, k: int = 1) -> list[dict]:
    """Chroma(chroma_cancel_category)에서 query와 가장 유사한 질문을 찾고,
    metadata.supabase_id로 Supabase(cancel_refund_faq)에서 실제 답변을 조회한다."""
    vectorstore = get_vectorstore(CHROMA_COLLECTION_NAME)
    results = vectorstore.similarity_search_with_relevance_scores(query, k=k)

    settings = get_settings()
    matches = []
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            for doc, score in results:
                supabase_id = doc.metadata.get("supabase_id")
                cur.execute(
                    "SELECT answer FROM cancel_refund_faq WHERE id = %s", (supabase_id,)
                )
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


def test_search_phone_broken() -> None:
    """테스트: '휴대폰이 부서졌는데, 어떻게 하는 것이 좋을까?' 질문으로 검색해 결과를 출력한다."""
    query = "휴대폰이 부서졌는데, 어떻게 하는 것이 좋을까?"
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
    command = args[0] if args and not args[0].startswith("--") else "build"
    dry_run = "--dry-run" in args

    #build_qa_pairs(dry_run=dry_run)
    #ingest_supabase(dry_run=dry_run)
    #ingest_chroma(dry_run=dry_run)
    test_search_phone_broken()
