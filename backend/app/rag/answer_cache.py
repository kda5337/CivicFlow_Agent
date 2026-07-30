"""담당자가 검토·확정한 최종 답변을 재사용하기 위한 캐시.

query_cache.py(분류 결과 재사용용, create_submission에서 씀)와는 목적과 저장 시점이
다른 별도 컬렉션/테이블이다:
- query_cache: 분류만 끝난(아직 아무도 검토 안 한) 결과를 문의 접수 시점에 재사용
- answer_cache(이 파일): 담당자가 "검토 완료 & 등록"을 눌러 실제로 승인한 답변을,
  다른 담당자가 "AI 처리"를 실행하는 시점에 재사용

실제 페이로드(질문 원문/답변 본문/출처)는 Supabase의 answer_cache 테이블에 정형 컬럼으로
저장한다. Chroma(answer_cache 컬렉션)에는 raw_text 임베딩과 이 테이블의 id만
metadata.cache_id로 남겨, 검색된 질문에서 실제 답변을 다시 조회하는 구조로 쓴다
(citizen_submissions와 무관하게 독립적으로 굴러가므로, 실제 문의에서 확정된 답변뿐
아니라 seed_query_cache.py로 미리 심어둔 예시 문답도 같은 방식으로 담을 수 있다).
"""

import uuid

import psycopg2

from app.core.config import get_settings
from app.rag.vectorstore import get_vectorstore

ANSWER_CACHE_COLLECTION_NAME = "answer_cache"

# query_cache보다 더 엄격하게 잡았다 — 여기서 재사용되는 건 분류가 아니라 사람이
# 검토·승인한 답변 본문 그 자체라, 잘못 재사용됐을 때의 체감 문제가 더 크다.
ANSWER_CACHE_SIMILARITY_THRESHOLD = 0.90


def lookup_answer_cache_entry(raw_text: str, threshold: float = ANSWER_CACHE_SIMILARITY_THRESHOLD) -> dict | None:
    """raw_text와 가장 유사한, 이미 확정 답변이 있는 과거 문의를 찾아 답변까지 돌려준다.

    임계값 미만이거나 컬렉션이 비어있으면 None을 반환한다. 히트하면 Chroma가 가진
    cache_id로 answer_cache 테이블을 조회해 final_answer/sources를 바로 담아 돌려준다.
    """
    vectorstore = get_vectorstore(ANSWER_CACHE_COLLECTION_NAME)
    results = vectorstore.similarity_search_with_relevance_scores(raw_text, k=1)
    if not results:
        return None

    doc, score = results[0]
    if score < threshold:
        return None

    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT final_answer, sources FROM answer_cache WHERE id = %s",
                (doc.metadata["cache_id"],),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None

    final_answer, sources = row
    return {
        "final_answer": final_answer,
        "sources": sources or [],
        "matched_question": doc.page_content,
        "score": score,
    }


def store_answer_cache_entry(
    raw_text: str,
    final_answer: str,
    sources: list[str],
    requires_manager_review: bool,
    submission_id: str | None = None,
) -> bool:
    """담당자가 확정한 답변을 answer_cache 테이블 + Chroma 양쪽에 등록한다.

    관리자검토가 필요했던 건(rule_flags.requires_manager_review)은 건너뛴다 —
    query_cache의 동일한 정책과 같은 이유로, 민감 민원은 텍스트가 비슷해도 매번
    사람이 다시 판단해야 한다. submission_id는 이 캐시 항목이 실제 어느 확정 문의에서
    왔는지 추적하기 위한 것으로, seed 데이터처럼 실제 문의 없이 넣는 경우엔 None으로 둔다.
    """
    if requires_manager_review:
        return False

    cache_id = str(uuid.uuid4())

    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO answer_cache (id, raw_text, final_answer, sources, submission_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (cache_id, raw_text, final_answer, sources, submission_id),
            )
        conn.commit()
    finally:
        conn.close()

    vectorstore = get_vectorstore(ANSWER_CACHE_COLLECTION_NAME)
    vectorstore.add_texts(
        texts=[raw_text],
        metadatas=[{"cache_id": cache_id}],
        ids=[cache_id],
    )
    return True


def list_answer_cache_entries() -> list[dict]:
    """지식베이스 관리 화면의 '답변 캐시' 섹션에 보여줄 전체 목록(최신순)."""
    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, raw_text, final_answer, sources, submission_id, created_at "
                "FROM answer_cache ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": str(row[0]),
            "raw_text": row[1],
            "final_answer": row[2],
            "sources": row[3] or [],
            "submission_id": str(row[4]) if row[4] else None,
            "created_at": row[5].isoformat(),
        }
        for row in rows
    ]


def delete_answer_cache_entry(cache_id: str) -> bool:
    """캐시 항목 하나를 Supabase(answer_cache 행)와 Chroma(임베딩) 양쪽에서 지운다.

    이후로는 이 항목이 아무리 비슷한 문의가 와도 더 이상 재사용되지 않는다.
    없는 id면 False를 돌려준다."""
    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM answer_cache WHERE id = %s RETURNING id", (cache_id,))
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    if not row:
        return False

    vectorstore = get_vectorstore(ANSWER_CACHE_COLLECTION_NAME)
    vectorstore._collection.delete(ids=[cache_id])
    return True
