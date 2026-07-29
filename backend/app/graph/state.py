from typing import Optional, TypedDict


class InquiryState(TypedDict, total=False):
    """LangGraph 노드 간에 공유되는 상태.

    각 노드는 자신이 담당하는 키만 채워서 반환하고,
    LangGraph가 이전 상태와 merge 한다.
    """

    inquiry_id: str
    raw_text: str
    received_at: str

    # 사용자용 접수 페이지(/submit)를 거쳐 이미 한 번 분류에 성공한 문의를 담당자가
    # "AI 처리"로 다시 돌릴 때 True로 들어온다. intake의 관련여부 판별은 별도의 LLM
    # 호출이라 최초 분류와 판단이 엇갈릴 수 있는데(예: 감정적 표현이 섞인 불만/신고를
    # 무관함으로 오판), 이미 사용자가 전용 문의 접수 양식을 통해 제출한 건은 관련성이
    # 이미 확인된 것으로 보고 이 판별을 건너뛴다.
    skip_relevance_check: bool
    cache_hit: bool  # query_cache에서 유사한 과거 문의를 찾아 재사용했는지 여부

    relevance_check: dict  # RelevanceCheckResult.model_dump()
    intake_reply: str  # 발랄한 페르소나로 생성한 재질문 요청/환영+요약 답변

    classification: dict  # ClassificationResult.model_dump()
    rule_flags: dict  # {"matched_rules": [...], "candidate_departments": [...], "requires_manager_review": bool, "review_reasons": [...]}

    retrieved_docs: list[dict]  # [{"content", "source", "score"}, ...]
    draft_answer: Optional[str]
    sources: list[str]  # 답변 본문과 분리된, 화면에 그대로(수정 불가) 보여줄 출처 라벨 목록

    status: str  # "pending_review" | "urgent_manager_review" | "irrelevant_input"
