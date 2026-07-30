from datetime import datetime, timezone

from app.core.llm import get_structured_llm
from app.graph.prompts import RELEVANCE_PROMPT
from app.graph.state import InquiryState
from app.models.schemas import RelevanceCheckResult


def check_relevance(text: str) -> RelevanceCheckResult:
    """사용자 입력이 이 시스템이 처리하는 민원·문의 대상 질문인지 LLM으로 판별한다."""
    llm = get_structured_llm(RelevanceCheckResult)
    return llm.invoke(RELEVANCE_PROMPT.format(text=text))


def intake_node(state: InquiryState) -> dict:
    """문의접수 노드. 입력을 검증하고, 처리 대상 질문인지 판별한 뒤 접수 시각을 기록한다.

    관련여부 판별 결과에 따른 분기(재질문 요청 vs 파이프라인 계속)는
    build.py의 라우팅과 nodes/intake_reply.py가 맡는다.
    """
    text = state["raw_text"].strip()
    if not text:
        raise ValueError("raw_text가 비어 있습니다.")

    if state.get("skip_relevance_check"):
        relevance_check = {
            "관련여부": True,
            "판단근거": "사용자용 문의 접수 페이지를 통해 제출된 문의라 관련성 확인을 생략함",
        }
    else:
        relevance_check = check_relevance(text).model_dump()

    return {
        "raw_text": text,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "relevance_check": relevance_check,
    }
