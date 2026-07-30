import psycopg2

from app.core.config import get_settings
from app.core.tracing import get_langfuse_client
from app.graph.state import InquiryState
from app.rag.knowledge_base import FAQ_TABLES as _FAQ_ANSWER_TABLES
from app.rag.vectorstore import get_vectorstore

MERGED_FAQ_COLLECTION_NAME = "chroma_merged_faq"

# coupang_faq와 컬럼 구성이 동일한(faq_id 제외) 테이블들 — PDF파일명+번호 또는 URL로
# 출처를 조립하는 로직을 그대로 공유한다.
_PDF_STYLE_TABLES = {
    "coupang_faq",
    "coupang_faq_personal_info",
    "coupang_faq_delivery",
    "coupang_faq_order_payment",
}

# 부서별로 생성된 FAQ 테이블들 — 컬럼 구성이 동일하고(id/source_index 또는 source_id/
# question/answer/source/department), "부서명 자주묻는 질문 N번" 형태로 출처를 조립하는
# 로직을 그대로 공유한다. (department, index_column) 형태.
_DEPARTMENT_FAQ_TABLES = {
    "it_support_faq": ("IT지원팀", "source_index"),
    "marketing_promotion_faq": ("마케팅팀", "source_id"),
    "admin_team_faq": ("행정팀", "source_index"),
    "legal_team_faq": ("법무팀", "source_index"),
    "sensitive_complaint_faq": ("고객지원총괄팀", "source_index"),
    "safety_team_faq": ("안전관리팀", "source_index"),
}


def _fetch_faq_row(cur, source_table: str, supabase_id) -> dict:
    """FAQ 테이블에서 답변과 출처 표시용 라벨을 함께 조회한다.

    coupang_faq/coupang_faq_personal_info는 PDF에서 온 항목이면 "파일명 N번 질문"으로,
    PDF에 없는 항목(예: return_policy.json 유래)이면 원본 source_url로 출처를 보여준다.
    duty_free_faq는 "공공데이터포털(데이터셋번호) 데이터셋명 - 자주묻는질문타입 N번째 질문"
    형태로, 어느 공공데이터의 어떤 정보인지 보여준다. 부서별 생성 FAQ 테이블들은
    "부서명 자주묻는 질문 N번"으로, 몇 번째 질문에서 온 답변인지 보여준다.
    """
    fallback_source = f"{source_table}:{supabase_id}"

    if source_table in _DEPARTMENT_FAQ_TABLES:
        department, index_column = _DEPARTMENT_FAQ_TABLES[source_table]
        cur.execute(
            f"SELECT answer, {index_column} FROM {source_table} WHERE id = %s",
            (supabase_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"answer": None, "source": fallback_source}
        answer, index = row
        source = f"{department} 자주묻는 질문 {index}번" if index is not None else f"{department} 자주묻는 질문"
        return {"answer": answer, "source": source}

    if source_table in _PDF_STYLE_TABLES:
        cur.execute(
            f"SELECT answer, source_pdf_file, source_pdf_question_number, source_url "
            f"FROM {source_table} WHERE id = %s",
            (supabase_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"answer": None, "source": fallback_source}
        answer, source_pdf_file, source_pdf_question_number, source_url = row
        if source_pdf_file:
            source = f"{source_pdf_file} {source_pdf_question_number}번 질문"
        else:
            source = source_url or fallback_source
        return {"answer": answer, "source": source}

    if source_table == "duty_free_faq":
        cur.execute(
            "SELECT answer, faq_type, source_dataset_id, source_dataset_name, "
            "source_faq_type_index FROM duty_free_faq WHERE id = %s",
            (supabase_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"answer": None, "source": fallback_source}
        answer, faq_type, source_dataset_id, source_dataset_name, source_faq_type_index = row
        if source_dataset_id and source_dataset_name:
            source = f"공공데이터포털({source_dataset_id}) {source_dataset_name}"
            if faq_type and source_faq_type_index:
                source += f" - {faq_type} {source_faq_type_index}번째 질문"
        else:
            source = fallback_source
        return {"answer": answer, "source": source}

    cur.execute(f"SELECT answer FROM {source_table} WHERE id = %s", (supabase_id,))
    row = cur.fetchone()
    return {"answer": row[0] if row else None, "source": fallback_source}


def _retrieve_from_merged_faq(query: str, top_k: int) -> list[dict]:
    """chroma_merged_faq에서 질문을 검색하고, metadata.source_table로 Supabase
    (duty_free_faq/coupang_faq)에서 실제 답변을 역참조한다."""
    settings = get_settings()
    results = get_vectorstore(MERGED_FAQ_COLLECTION_NAME).similarity_search_with_relevance_scores(
        query, k=top_k
    )

    retrieved_docs = []
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            for doc, score in results:
                source_table = doc.metadata.get("source_table")
                supabase_id = doc.metadata.get("supabase_id")

                if source_table in _FAQ_ANSWER_TABLES:
                    faq_row = _fetch_faq_row(cur, source_table, supabase_id)
                else:
                    faq_row = {"answer": None, "source": f"{source_table}:{supabase_id}"}

                retrieved_docs.append(
                    {
                        "content": f"질문: {doc.page_content}\n답변: {faq_row['answer'] or '(답변을 찾을 수 없음)'}",
                        "source": faq_row["source"],
                        "score": score,
                    }
                )
    finally:
        conn.close()

    return retrieved_docs


def retrieve_node(state: InquiryState) -> dict:
    """8절: RAG 근거 검색 노드. 문의와 유사한 FAQ를 Top-K로 검색한다.

    knowledge_base 컬렉션은 아직 실제 문서가 적재되어 있지 않아(0건), 문의유형/매칭된
    Rule과 무관하게 항상 chroma_merged_faq(면세점+쿠팡 FAQ 질문 임베딩)에서 검색하고,
    Supabase에서 실제 답변을 역참조한다. knowledge_base에 실제 문서가 채워지면,
    문의유형에 따라 컬렉션을 다시 나누는 조건부 분기를 되살리면 된다.

    Chroma의 similarity_search는 LangChain 콜백을 발생시키지 않으므로,
    Langfuse에서 'retriever' 타입으로 정확히 보이도록 span을 직접 만든다.
    """
    settings = get_settings()
    query = state["raw_text"]

    with get_langfuse_client().start_as_current_observation(
        name="rag-retrieve-topk",
        as_type="retriever",
        input=query,
        metadata={
            "top_k": settings.rag_top_k,
            "vectorstore": "chroma",
            "collection": MERGED_FAQ_COLLECTION_NAME,
        },
    ) as span:
        retrieved_docs = _retrieve_from_merged_faq(query, settings.rag_top_k)

        span.update(
            output=[
                {"source": d["source"], "score": d["score"]} for d in retrieved_docs
            ]
        )

    return {"retrieved_docs": retrieved_docs}