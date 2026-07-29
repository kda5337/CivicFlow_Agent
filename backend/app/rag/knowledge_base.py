import psycopg2
from langchain_core.documents import Document

from app.core.config import get_settings
from app.rag.vectorstore import get_vectorstore

MERGED_FAQ_COLLECTION_NAME = "chroma_merged_faq"

# retrieve_node가 실제로 검색에 쓰는 Supabase FAQ 테이블 전체 목록(11개) + 지식베이스
# 관리 화면에 보여줄 한글 라벨. 이 목록이 retrieve.py의 _FAQ_ANSWER_TABLES와 같은
# 화이트리스트 역할도 한다 — 새 출처를 추가하려면 여기 하나만 늘리면 된다.
FAQ_SOURCES = [
    {"table": "coupang_faq", "label": "쿠팡 전체 FAQ"},
    {"table": "coupang_faq_delivery", "label": "쿠팡 배송 FAQ"},
    {"table": "coupang_faq_order_payment", "label": "쿠팡 주문/결제 FAQ"},
    {"table": "coupang_faq_personal_info", "label": "쿠팡 개인정보 FAQ"},
    {"table": "duty_free_faq", "label": "면세점 FAQ"},
    {"table": "admin_team_faq", "label": "행정팀 FAQ"},
    {"table": "it_support_faq", "label": "IT지원팀 FAQ"},
    {"table": "legal_team_faq", "label": "법무팀 FAQ"},
    {"table": "safety_team_faq", "label": "안전팀 FAQ"},
    {"table": "marketing_promotion_faq", "label": "마케팅팀 FAQ"},
    {"table": "sensitive_complaint_faq", "label": "민감 민원 FAQ"},
]

FAQ_TABLES = {source["table"] for source in FAQ_SOURCES}
_LABELS = {source["table"]: source["label"] for source in FAQ_SOURCES}


class KnowledgeBaseItemNotFound(Exception):
    """수정/삭제하려는 id가 그 테이블에 없을 때. 잘못된 table(ValueError)과 구분해
    라우터가 404로 매핑할 수 있게 별도 예외로 둔다."""


def _embedded_count(vectorstore, table: str) -> int:
    result = vectorstore._collection.get(where={"source_table": table}, include=[])
    return len(result["ids"])


def _summarize(cur, vectorstore, table: str) -> dict:
    # table은 항상 FAQ_TABLES 화이트리스트에서만 온 값이라 f-string 삽입이 안전하다.
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row_count = cur.fetchone()[0]
    embedded_count = _embedded_count(vectorstore, table)
    return {
        "table": table,
        "label": _LABELS[table],
        "row_count": row_count,
        "embedded_count": embedded_count,
        "in_sync": row_count == embedded_count,
    }


def get_source_summaries() -> list[dict]:
    """지식베이스 관리 화면용: 출처 테이블마다 Supabase 실제 건수와 Chroma
    (chroma_merged_faq)에 임베딩된 건수를 나란히 보여줘, 재처리가 필요한지 알 수 있게 한다."""
    settings = get_settings()
    vectorstore = get_vectorstore(MERGED_FAQ_COLLECTION_NAME)
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            return [_summarize(cur, vectorstore, source["table"]) for source in FAQ_SOURCES]
    finally:
        conn.close()


def get_source_items(table: str) -> list[dict]:
    """지식베이스 관리 화면에서 한 출처를 펼쳐볼 때 쓴다. 11개 테이블 모두 id/question/
    answer 컬럼 구성이 같아서(그 위에 테이블마다 다른 부가 컬럼이 더 있을 뿐) 이 세
    컬럼만으로 공통으로 조회할 수 있다."""
    if table not in FAQ_TABLES:
        raise ValueError(f"알 수 없는 지식베이스 출처입니다: {table}")

    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, question, answer FROM {table} ORDER BY id")
            rows = cur.fetchall()
    finally:
        conn.close()

    return [{"id": row[0], "question": row[1], "answer": row[2]} for row in rows]


# Chroma는 where에 키가 2개 이상이면 암묵적 AND를 허용하지 않고 $and를 요구한다
# (단일 키 {"source_table": table}는 reprocess_source처럼 그대로 써도 된다).
def _item_where(table: str, item_id: int) -> dict:
    return {"$and": [{"source_table": table}, {"supabase_id": item_id}]}


def _replace_embedding(vectorstore, table: str, item_id: int, question: str) -> None:
    """한 항목(id)의 임베딩만 지우고 새 질문으로 다시 만든다. 테이블 전체를 다시
    돌지 않아도 되게, 추가/수정/삭제 각각 이 항목 하나만 반영한다."""
    vectorstore._collection.delete(where=_item_where(table, item_id))
    vectorstore.add_documents(
        [Document(page_content=question, metadata={"source_table": table, "supabase_id": item_id})]
    )


# 11개 테이블 모두 question/answer 말고도 source TEXT NOT NULL 컬럼을 갖고 있다
# (기존 ingest_*.py는 각자 실제 출처 문자열을 채운다). 담당자가 화면에서 직접
# 추가하는 항목에는 그런 원본 출처가 없으니 이 값으로 남긴다. faq_id/source_index
# 처럼 테이블마다 이름이 다른 "원본 순번" NOT NULL UNIQUE 컬럼들은 수동 추가 항목이
# 채울 자연스러운 값이 없어 nullable로 마이그레이션해뒀다 — INSERT에서 아예 뺀다.
_MANUAL_SOURCE_LABEL = "담당자 직접 입력"


def create_item(table: str, question: str, answer: str) -> dict:
    """새 FAQ 항목을 Supabase에 추가하고 그 질문만 바로 임베딩한다(변경 이력은
    남기지 않는다 — 수정/삭제도 마찬가지로 기존 값을 덮어쓸 뿐이다)."""
    if table not in FAQ_TABLES:
        raise ValueError(f"알 수 없는 지식베이스 출처입니다: {table}")

    settings = get_settings()
    vectorstore = get_vectorstore(MERGED_FAQ_COLLECTION_NAME)

    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {table} (question, answer, source) VALUES (%s, %s, %s) RETURNING id",
                (question, answer, _MANUAL_SOURCE_LABEL),
            )
            item_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    vectorstore.add_documents(
        [Document(page_content=question, metadata={"source_table": table, "supabase_id": item_id})]
    )
    return {"id": item_id, "question": question, "answer": answer}


def update_item(table: str, item_id: int, question: str, answer: str) -> dict:
    """기존 항목의 질문/답변을 덮어쓰고, 임베딩도 새 질문으로 다시 만든다."""
    if table not in FAQ_TABLES:
        raise ValueError(f"알 수 없는 지식베이스 출처입니다: {table}")

    settings = get_settings()
    vectorstore = get_vectorstore(MERGED_FAQ_COLLECTION_NAME)

    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {table} SET question = %s, answer = %s WHERE id = %s RETURNING id",
                (question, answer, item_id),
            )
            row = cur.fetchone()
            if row is None:
                raise KnowledgeBaseItemNotFound(f"{table}에 id={item_id} 항목이 없습니다")
        conn.commit()
    finally:
        conn.close()

    _replace_embedding(vectorstore, table, item_id, question)
    return {"id": item_id, "question": question, "answer": answer}


def delete_item(table: str, item_id: int) -> None:
    """항목을 Supabase에서 지우고 그 임베딩도 함께 지운다."""
    if table not in FAQ_TABLES:
        raise ValueError(f"알 수 없는 지식베이스 출처입니다: {table}")

    settings = get_settings()
    vectorstore = get_vectorstore(MERGED_FAQ_COLLECTION_NAME)

    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE id = %s RETURNING id", (item_id,))
            row = cur.fetchone()
            if row is None:
                raise KnowledgeBaseItemNotFound(f"{table}에 id={item_id} 항목이 없습니다")
        conn.commit()
    finally:
        conn.close()

    vectorstore._collection.delete(where=_item_where(table, item_id))


def reprocess_source(table: str) -> dict:
    """한 출처 테이블의 질문을 Supabase 현재 상태 기준으로 Chroma에 다시 임베딩한다.

    data.go.kr 같은 외부 API를 다시 호출하지는 않는다(그건 각 ingest_*.py 스크립트의
    fetch 단계 몫) — 여기서는 이미 Supabase에 적재된 question 컬럼만 다시 읽어 기존
    임베딩을 지우고 새로 만든다. Supabase 쪽 데이터가 스크립트로 갱신된 뒤 Chroma가
    거기 맞춰 밀려버렸거나(예: 컬렉션 초기화) 둘이 어긋났을 때 되돌리는 용도다.
    """
    if table not in FAQ_TABLES:
        raise ValueError(f"알 수 없는 지식베이스 출처입니다: {table}")

    settings = get_settings()
    vectorstore = get_vectorstore(MERGED_FAQ_COLLECTION_NAME)

    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, question FROM {table} ORDER BY id")
            rows = cur.fetchall()

            # 화이트리스트 안에서 온 table이라 안전하다. 기존 임베딩을 먼저 지우고
            # 새로 채워야, 삭제된 행이 임베딩에만 남아 계속 검색되는 일이 없다.
            vectorstore._collection.delete(where={"source_table": table})

            if rows:
                documents = [
                    Document(page_content=question, metadata={"source_table": table, "supabase_id": row_id})
                    for row_id, question in rows
                ]
                vectorstore.add_documents(documents)

            return {
                "table": table,
                "label": _LABELS[table],
                "row_count": len(rows),
                "embedded_count": len(rows),
                "in_sync": True,
            }
    finally:
        conn.close()
