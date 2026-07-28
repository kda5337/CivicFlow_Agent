from typing import Optional, TypedDict


class InquiryState(TypedDict, total=False):
    """LangGraph 노드 간에 공유되는 상태.

    각 노드는 자신이 담당하는 키만 채워서 반환하고,
    LangGraph가 이전 상태와 merge 한다.
    """

    inquiry_id: str
    raw_text: str
    received_at: str

    cache_hit: bool  # query_cache에서 유사한 과거 문의를 찾아 재사용했는지 여부

    relevance_check: dict  # RelevanceCheckResult.model_dump()
    intake_reply: str  # 발랄한 페르소나로 생성한 재질문 요청/환영+요약 답변

    classification: dict  # ClassificationResult.model_dump()
    rule_flags: dict  # {"matched_rules": [...], "candidate_departments": [...], "requires_manager_review": bool, "review_reasons": [...]}

    retrieved_docs: list[dict]  # [{"content", "source", "score"}, ...]
    draft_answer: Optional[str]
    sources: list[str]  # 답변 본문과 분리된, 화면에 그대로(수정 불가) 보여줄 출처 라벨 목록

    status: str  # "pending_review" | "urgent_manager_review" | "irrelevant_input"
