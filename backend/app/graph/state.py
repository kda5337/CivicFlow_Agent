from typing import Optional, TypedDict


class InquiryState(TypedDict, total=False):
    """LangGraph 노드 간에 공유되는 상태.

    각 노드는 자신이 담당하는 키만 채워서 반환하고,
    LangGraph가 이전 상태와 merge 한다.
    """

    inquiry_id: str
    raw_text: str
    received_at: str

    relevance_check: dict  # RelevanceCheckResult.model_dump()
    intake_reply: str  # 발랄한 페르소나로 생성한 재질문 요청/환영+요약 답변

    classification: dict  # ClassificationResult.model_dump()
    rule_flags: dict  # {"matched_rules": [...], "candidate_departments": [...], "requires_manager_review": bool, "review_reasons": [...]}

    retrieved_docs: list[dict]  # [{"content", "source", "score"}, ...]
    draft_answer: Optional[str]

    status: str  # "pending_review" | "urgent_manager_review" | "irrelevant_input"
