from app.core.llm import get_structured_llm
from app.graph.prompts import CLASSIFY_PROMPT
from app.graph.state import InquiryState
from app.models.schemas import LLMClassification


def classify_node(state: InquiryState) -> dict:
    """7절: LLM 유형 분류 노드. 문의유형/핵심요청/감정상태만 구조화된 JSON으로 분류한다.

    담당부서/우선순위는 여기서 정하지 않는다 — rules_node가 rules.yaml만으로 채운다.
    """
    llm = get_structured_llm(LLMClassification)
    result: LLMClassification = llm.invoke(
        CLASSIFY_PROMPT.format(text=state["raw_text"])
    )
    return {"classification": result.model_dump()}
