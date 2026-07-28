from typing import Literal, Optional

from pydantic import BaseModel, Field


class RelevanceCheckResult(BaseModel):
    """접수 단계에서 입력이 이 시스템의 처리 대상(민원·문의)인지 판별한 결과."""

    관련여부: bool = Field(description="민원·문의(신청/변경/취소·환불/오류·장애/졸업요건·교육과정 등)와 관련이 있는지 여부")
    판단근거: str = Field(description="관련여부를 그렇게 판단한 짧은 근거")


class LLMClassification(BaseModel):
    """7절 AI 분류 프롬프트가 실제로 LLM에게 요청하는 출력 스키마.

    담당부서/우선순위는 여기 없다 — LLM의 판단 대상이 아니라 rules.yaml이 전담해서
    결정하는 필드이기 때문이다(rules_node가 classify 다음 단계에서 채운다).
    """

    문의유형: Literal[
        "신청/등록", "변경/정정", "취소/환불", "오류/장애", "불만/신고", "안내/조회", "일반문의"
    ]
    핵심요청: str = Field(description="문의에서 담당자가 처리해야 할 핵심 요청 요약")
    감정상태: Literal["긍정", "중립", "부정", "불만"]
    분류근거: str = Field(description="왜 이렇게 분류했는지에 대한 짧은 근거")


class ClassificationResult(BaseModel):
    """rules_node까지 적용을 마친 최종 분류 결과 스키마. API 응답 등에서 사용한다."""

    문의유형: Literal[
        "신청/등록", "변경/정정", "취소/환불", "오류/장애", "불만/신고", "안내/조회", "일반문의"
    ]
    핵심요청: str
    감정상태: Literal["긍정", "중립", "부정", "불만"]
    우선순위: Literal["낮음", "보통", "높음", "최상"] = Field(
        description="rules.yaml의 우선순위 규칙으로만 결정된다 (LLM은 판단하지 않음)"
    )
    담당부서: str = Field(
        description="rules.yaml의 담당부서 규칙으로만 결정된다 (LLM은 판단하지 않음)"
    )
    분류근거: str


class CurriculumSQLQuery(BaseModel):
    """졸업요건_문의/교육과정_문의 Rule에 걸린 문의에 답하기 위해 LLM이 생성한 조회 SQL."""

    sql: str = Field(
        description="graduation_requirements/curriculum_courses 테이블만 사용하는 단일 SELECT 문"
    )


class RetrievedDoc(BaseModel):
    content: str
    source: str
    score: float


class InquiryRequest(BaseModel):
    text: str


class InquiryResponse(BaseModel):
    inquiry_id: str
    raw_text: str
    relevance_check: Optional[RelevanceCheckResult] = None
    intake_reply: Optional[str] = Field(
        default=None, description="발랄한 페르소나로 생성한 재질문 요청/환영+요약 답변"
    )
    classification: Optional[ClassificationResult] = None
    rule_flags: dict = Field(default_factory=dict)
    retrieved_docs: list[RetrievedDoc] = Field(default_factory=list)
    draft_answer: Optional[str] = None
    status: str
    trace_url: Optional[str] = Field(
        default=None, description="이 처리 과정의 Langfuse 트레이스 링크 (담당자 디버깅용)"
    )
