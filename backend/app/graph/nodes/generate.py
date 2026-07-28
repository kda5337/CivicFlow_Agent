from app.core.llm import get_llm
from app.graph.prompts import GENERATE_PROMPT
from app.graph.state import InquiryState

# retrieved_docs[].source의 내부 식별자를 사람이 읽기 좋은 출처 라벨로 바꾼다.
# 매핑에 없는 값(knowledge_base 문서의 source=파일명 등)은 그대로 보여준다.
_SOURCE_LABELS = {
    "curriculum_db(SQL)": "학사정보 시스템(교육과정/졸업요건 조회)",
}


def _format_context(retrieved_docs: list[dict]) -> str:
    if not retrieved_docs:
        return "(검색된 근거 문서 없음)"
    return "\n".join(
        f"- [{doc['source']}] {doc['content']}" for doc in retrieved_docs
    )


def _friendly_source_label(source: str) -> str:
    if source in _SOURCE_LABELS:
        return _SOURCE_LABELS[source]
    if source.startswith("coupang_faq:"):
        return "쿠팡 고객센터 자주묻는 질문"
    if source.startswith("duty_free_faq:"):
        return "제주관광공사 온라인면세점 자주묻는 질문"
    if source.startswith("it_support_faq:"):
        return "IT지원팀 자주묻는 질문"
    if source.startswith("marketing_promotion_faq:"):
        return "마케팅팀 자주묻는 질문"
    if source.startswith("admin_team_faq:"):
        return "행정팀 자주묻는 질문"
    if source.startswith("safety_team_faq:"):
        return "안전관리팀 자주묻는 질문"
    if source.startswith("legal_team_faq:"):
        return "법무팀 자주묻는 질문"
    if source.startswith("sensitive_complaint_faq:"):
        return "고객지원총괄팀 자주묻는 질문"
    return source


def _format_sources_footer(retrieved_docs: list[dict]) -> str:
    """LLM이 아닌 코드가 직접 만드는 출처 목록. 답변 본문에 없는 근거를 지어내거나
    실제로 참고한 근거를 누락하는 일이 없도록, retrieved_docs를 그대로 순회해 만든다."""
    if not retrieved_docs:
        return ""

    labels = []
    seen = set()
    for doc in retrieved_docs:
        label = _friendly_source_label(doc["source"])
        if label not in seen:
            seen.add(label)
            labels.append(label)

    bullet_list = "\n".join(f"- {label}" for label in labels)
    return f"\n\n---\n참고 자료:\n{bullet_list}"


def generate_node(state: InquiryState) -> dict:
    """답변 초안 생성 노드. 분류 결과 + RAG 근거를 결합해 초안을 만든다."""
    llm = get_llm(temperature=0.3)
    classification = state.get("classification") or {}
    retrieved_docs = state.get("retrieved_docs", [])

    prompt = GENERATE_PROMPT.format(
        text=state["raw_text"],
        문의유형=classification.get("문의유형", "미분류"),
        우선순위=classification.get("우선순위", "보통"),
        담당부서=classification.get("담당부서", "미배정"),
        context=_format_context(retrieved_docs),
    )

    response = llm.invoke(prompt)
    draft_answer = response.content + _format_sources_footer(retrieved_docs)
    return {
        "draft_answer": draft_answer,
        "status": "pending_review",
    }
