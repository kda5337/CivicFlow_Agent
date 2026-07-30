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
    # retrieve.py의 _fetch_faq_row가 대부분의 테이블(부서별 생성 FAQ, PDF 유래
    # coupang_faq/duty_free_faq)은 이미 "부서명/파일명 N번 질문" 형태로 조립해서 내려주므로
    # 여기서 다시 예쁘게 바꿀 필요가 없다 — 이 매핑은 그 조립이 실패했을 때(예: source_pdf_file/
    # source_url이 둘 다 없어 fallback_source="테이블명:id" 그대로 내려온 경우)의 최후 수단이다.
    if source in _SOURCE_LABELS:
        return _SOURCE_LABELS[source]
    if source.startswith("coupang_faq:"):
        return "쿠팡 고객센터 자주묻는 질문"
    if source.startswith("duty_free_faq:"):
        return "제주관광공사 온라인면세점 자주묻는 질문"
    return source


def _friendly_sources(retrieved_docs: list[dict]) -> list[str]:
    """LLM이 아닌 코드가 직접 만드는, 중복 제거된 출처 라벨 목록.

    답변 본문과 분리된 별도 값이다 — 화면에서 수정 가능한 텍스트(답변 본문)에 섞어
    넣지 않고, 그 자체로 수정 불가능한 요소로 그대로 보여주기 위한 것이다.
    """
    labels = []
    seen = set()
    for doc in retrieved_docs:
        label = _friendly_source_label(doc["source"])
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def build_draft_answer(raw_text: str, classification: dict, docs: list[dict]) -> tuple[str, list[str]]:
    """(답변 본문, 출처 라벨 목록)을 만든다. 답변 본문에는 출처를 섞어 넣지 않는다.

    generate_node(자동 생성, 문서 1건)와 담당자가 RAG 검색 결과 화면에서 직접 고른
    문서(들)로 다시 만드는 수동 재생성 엔드포인트가 이 함수를 공유한다 — 근거로 쓸
    문서가 몇 건이든 이 함수는 그대로 받아 처리하고, "몇 건을 근거로 쓸지"는 호출하는
    쪽이 결정한다.
    """
    llm = get_llm(temperature=0.3)
    prompt = GENERATE_PROMPT.format(
        text=raw_text,
        문의유형=classification.get("문의유형", "미분류"),
        우선순위=classification.get("우선순위", "보통"),
        담당부서=classification.get("담당부서", "미배정"),
        context=_format_context(docs),
    )
    response = llm.invoke(prompt)
    return response.content, _friendly_sources(docs)


def generate_node(state: InquiryState) -> dict:
    """답변 초안 생성 노드. 분류 결과 + RAG 근거를 결합해 초안을 만든다.

    retrieve_node는 이제 유사도 상위 RAG_TOP_K(현재 3)건을 전부 state["retrieved_docs"]에
    담아 RAG 검색 결과 화면에서 다 보여주지만, 자동 생성 시점에는 아직 가장 유사도가
    높은 1건만 근거로 쓴다 — 2·3순위 문서를 함께 근거로 섞으면 실제로 답변 품질이
    좋아지는지 아직 검증 전이라, 우선 기존과 동일한 단일 근거 문서 방식을 유지한다.
    담당자가 RAG 검색 결과 화면에서 다른 문서(들)를 직접 골라 재생성하고 싶다면
    /inquiries/regenerate-answer가 build_draft_answer를 문서 제한 없이 호출한다.
    """
    classification = state.get("classification") or {}
    retrieved_docs = state.get("retrieved_docs", [])
    draft_answer, sources = build_draft_answer(state["raw_text"], classification, retrieved_docs[:1])
    return {
        "draft_answer": draft_answer,
        "sources": sources,
        "status": "pending_review",
    }
