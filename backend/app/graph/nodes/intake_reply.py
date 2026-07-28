from app.core.llm import get_llm
from app.graph.prompts import IRRELEVANT_REPLY_PROMPT, WELCOME_REPLY_PROMPT
from app.graph.state import InquiryState


def generate_irrelevant_reply(text: str, reason: str) -> str:
    """관련 없는 입력에 대해, 또래 친구 같은 발랄한 말투로 재질문을 요청하는 답변을 생성한다."""
    llm = get_llm(temperature=0.5)
    prompt = IRRELEVANT_REPLY_PROMPT.format(text=text, reason=reason)
    return llm.invoke(prompt).content


def generate_welcome_reply(text: str) -> str:
    """정상 판정된 입력에 대해, 환영 인사 한 문장 + 질문 요약으로 이루어진 답변을 생성한다."""
    llm = get_llm(temperature=0.5)
    prompt = WELCOME_REPLY_PROMPT.format(text=text)
    return llm.invoke(prompt).content


def reject_node(state: InquiryState) -> dict:
    """intake에서 관련 없음으로 판별된 경우, 재질문을 요청하는 답변을 만들고 파이프라인을 종료한다."""
    relevance = state.get("relevance_check") or {}
    reply = generate_irrelevant_reply(state["raw_text"], relevance.get("판단근거", ""))
    return {
        "intake_reply": reply,
        "status": "irrelevant_input",
    }


def greet_node(state: InquiryState) -> dict:
    """intake에서 정상 판정된 경우, 환영 인사와 질문 요약이 담긴 첫 응답을 만든다."""
    reply = generate_welcome_reply(state["raw_text"])
    return {"intake_reply": reply}
