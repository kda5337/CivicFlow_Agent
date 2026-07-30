from app.core.tracing import get_langfuse_client
from app.graph.state import InquiryState


def _build_review_notice(state: InquiryState) -> str:
    """관리자 검토가 필요한 이유를 사용자 입력·문의유형·매칭된 규칙·우선순위 기준으로
    요약한 안내문을 만든다.

    LLM을 호출하지 않고 classification/rule_flags에 이미 있는 값만 그대로 조합한다 —
    이 분기는 "왜 이 판단이 났는지"를 있는 그대로 보여주는 게 목적이라, 문구를 새로
    지어내는 대신 결정론적으로 조립한다.
    """
    raw_text = state.get("raw_text", "")
    classification = state.get("classification") or {}
    rule_flags = state.get("rule_flags") or {}

    문의유형 = classification.get("문의유형", "미분류")
    우선순위 = classification.get("우선순위", "보통")
    담당부서 = classification.get("담당부서", "미배정")
    review_reasons = rule_flags.get("review_reasons", [])
    reasons_text = ", ".join(review_reasons) if review_reasons else "관리자 검토 규칙"

    return (
        "[관리자 검토가 필요한 문의입니다]\n\n"
        f'문의 내용: "{raw_text}"\n\n'
        "분류 결과:\n"
        f"- 문의유형: {문의유형}\n"
        f"- 우선순위: {우선순위}\n"
        f"- 담당부서(안): {담당부서}\n\n"
        f"'{reasons_text}' 규칙에 매칭되어 우선순위가 '{우선순위}'으로 판단되었고, "
        "자동 답변 대신 담당자의 직접 확인이 필요한 문의로 분류되었습니다.\n"
        "담당자가 확인 후 빠르게 연락드리겠습니다."
    )


def manager_review_node(state: InquiryState) -> dict:
    """민감 민원(9절 Rule) 감지 시 답변 초안 생성(generate_node)만 건너뛰고 즉시
    관리자 검토로 넘긴다. RAG 근거 검색(retrieve_node)은 이 분기 이전에 이미
    실행되어 state.retrieved_docs에 담겨 있다 — 관리자가 검토할 때 참고할 수
    있게 항상 근거를 확보해두기 위함이다.

    답변 자리에는 LLM이 만든 초안 대신, 왜 관리자 검토가 필요한지를 설명하는
    안내문(_build_review_notice)을 넣는다.

    이 분기를 탄 경우 자체가 운영자가 놓치면 안 되는 신호이므로,
    level=WARNING span으로 남겨 Langfuse에서 바로 눈에 띄게 한다.
    """
    with get_langfuse_client().start_as_current_observation(
        name="escalate-to-manager-review",
        as_type="span",
        level="WARNING",
        input={"matched_rules": state.get("rule_flags", {}).get("matched_rules", [])},
        output={"status": "urgent_manager_review"},
    ):
        pass

    return {
        "draft_answer": _build_review_notice(state),
        "status": "urgent_manager_review",
    }