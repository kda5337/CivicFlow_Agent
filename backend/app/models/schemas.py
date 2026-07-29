from typing import Literal, Optional

from pydantic import BaseModel, Field

InquiryType = Literal[
    "신청/등록", "변경/정정", "취소/환불", "오류/장애", "불만/신고", "안내/조회", "일반문의"
]


class RelevanceCheckResult(BaseModel):
    """접수 단계에서 입력이 이 시스템의 처리 대상(민원·문의)인지 판별한 결과."""

    관련여부: bool = Field(description="민원·문의(신청/변경/취소·환불/오류·장애/졸업요건·교육과정 등)와 관련이 있는지 여부")
    판단근거: str = Field(description="관련여부를 그렇게 판단한 짧은 근거")


class LLMClassification(BaseModel):
    """7절 AI 분류 프롬프트가 실제로 LLM에게 요청하는 출력 스키마.

    담당부서/우선순위는 여기 없다 — LLM의 판단 대상이 아니라 rules.yaml이 전담해서
    결정하는 필드이기 때문이다(rules_node가 classify 다음 단계에서 채운다).

    문의 하나가 여러 유형에 동시에 해당될 수 있어(예: "환불계좌를 변경하고 싶어요"는
    취소/환불이면서 변경/정정이기도 함), 해당되는 유형 전부(문의유형들)와 그중 실제
    라우팅에 쓸 대표 유형(주요문의유형)을 LLM이 함께 판단한다 — rules_node는 여전히
    주요문의유형 하나만 보고 기존 로직 그대로 동작한다.
    """

    문의유형들: list[InquiryType] = Field(
        description="문의 내용에 해당하는 문의유형을 모두 나열 (하나면 원소 1개짜리 리스트)"
    )
    주요문의유형: InquiryType = Field(
        description="문의유형들 중 사용자가 실제로 원하는 핵심 행동에 가장 해당하는 대표 유형 하나"
    )
    핵심요청: str = Field(description="문의에서 담당자가 처리해야 할 핵심 요청 요약")
    감정상태: Literal["긍정", "중립", "부정", "불만"]
    분류근거: str = Field(description="왜 이렇게 분류했는지에 대한 짧은 근거")


class ClassificationResult(BaseModel):
    """rules_node까지 적용을 마친 최종 분류 결과 스키마. API 응답 등에서 사용한다.

    문의유형은 LLM이 고른 주요문의유형이 그대로 들어온다(rules_node가 라우팅에 쓴 값과
    동일) — 하위 호환을 위해 필드명은 바꾸지 않았다. 문의유형들은 참고용으로 남겨둔
    전체 후보 목록이다.
    """

    문의유형: InquiryType
    문의유형들: list[InquiryType] = Field(
        default_factory=list, description="LLM이 판단한 해당 문의유형 전체 (참고용, 라우팅에는 문의유형만 쓰임)"
    )
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
    skip_relevance_check: bool = Field(
        default=False,
        description="사용자용 문의 접수 페이지를 거쳐 이미 분류된 문의를 '문의 접수함'에서 다시 AI 처리할 때 True. "
        "intake의 관련여부 판별(별도 LLM 호출)이 최초 분류와 엇갈려 재처리가 막히는 것을 방지한다.",
    )
    submission_id: Optional[str] = Field(
        default=None,
        description="문의 접수함에서 'AI 처리'로 넘어온 citizen_submissions 원본 건 id. 있으면 "
        "intake/classify/apply_rules를 다시 돌리지 않고, 그 원본 건에 이미 저장된 분류 결과(문의 "
        "등록 시점에 classify_node+rules_node가 이미 검증해 둔 것)를 그대로 가져와 RAG 검색+답변 "
        "생성만 수행한다.",
    )


class CitizenSubmissionRequest(BaseModel):
    """사용자용 문의 접수 페이지(/submit)에서 보내는 요청. AI 처리는 하지 않고
    citizen_submissions 테이블에 그대로 저장만 한다."""

    name: str
    contact: str
    raw_text: str


class CitizenSubmission(BaseModel):
    """담당자용 문의 접수함 목록 / 사용자용 문의 유형 자동 확인·처리 상태 조회·
    답변 확인·내 문의 내역이 전부 함께 쓰는 항목 하나.

    접수(INSERT) 직후 서버가 바로 classify_node+rules_node를 돌려 inquiry_type
    이하 필드를 채우고 status를 '검토중'으로 바꾼다(RAG 검색·답변 생성은 아직 안 함).
    이후 담당자가 내부 화면에서 실제 답변까지 만들어 확정하면 final_answer가 채워지고
    status가 '답변완료'가 된다. 문의유형/담당부서를 담당자가 내부에서 고쳤다면 그 결과가
    이 레코드에도 다시 반영된다(사용자 페이지에는 결과만 보이고 수정 버튼은 없다).
    """

    id: str
    name: str
    contact: str
    raw_text: str
    submitted_at: str
    status: str = "접수완료"
    inquiry_type: Optional[str] = Field(default=None, description="주요문의유형")
    inquiry_types: list[str] = Field(default_factory=list, description="문의유형들(해당되는 유형 전체)")
    department: Optional[str] = None
    candidate_departments: list[str] = Field(default_factory=list, description="담당부서 후보 전체")
    priority: Optional[str] = None
    emotion: Optional[str] = Field(default=None, description="감정상태")
    core_request: Optional[str] = Field(default=None, description="핵심요청")
    classification_reason: Optional[str] = Field(default=None, description="분류근거")
    requires_manager_review: bool = Field(
        default=False, description="rules.yaml 9절 민감 민원 규칙에 걸려 담당자의 즉시 검토가 필요한지 여부"
    )
    matched_rules: list[str] = Field(default_factory=list, description="rule_flags.matched_rules (규칙 엔진 매칭 경로)")
    final_answer: Optional[str] = None


class SubmissionClassificationUpdate(BaseModel):
    """담당자가 '문의 접수함'에서 AI 처리(전체 파이프라인)를 실행한 뒤, 그 분류
    결과를 원본 접수 건에 되돌려 기록할 때 보내는 요청 — 담당자가 화면에서 담당부서를
    직접 고쳤다면 그 값이 반영된다. status는 이 호출로 '검토중'이 된다."""

    inquiry_type: str
    inquiry_types: list[str] = Field(default_factory=list)
    department: str
    candidate_departments: list[str] = Field(default_factory=list)
    priority: str
    emotion: Optional[str] = None
    core_request: Optional[str] = None
    classification_reason: Optional[str] = None
    requires_manager_review: bool = False


class SubmissionAnswerUpdate(BaseModel):
    """담당자가 답변 초안 화면에서 '최종 답변으로 저장'을 눌렀을 때 보내는 요청.
    status는 이 호출로 자동으로 '답변완료'가 된다."""

    final_answer: str


class RegenerateAnswerRequest(BaseModel):
    """담당자가 RAG 검색 결과 화면에서 문서를 직접 골라 답변을 다시 만들 때 보내는 요청.

    intake/classify/apply_rules/retrieve는 이미 끝난 뒤라 다시 돌 필요가 없어서,
    그 결과(원문/분류 결과)와 이번에 근거로 쓸 문서(들)만 받는다."""

    raw_text: str
    classification: dict
    docs: list[RetrievedDoc] = Field(description="근거로 쓸 문서. 1개면 단일 근거, 여러 개면 함께 근거로 삼는다")


class RegenerateAnswerResponse(BaseModel):
    draft_answer: str
    sources: list[str] = Field(
        default_factory=list, description="답변 본문과 분리된, 화면에 수정 불가 요소로 그대로 보여줄 출처 라벨 목록"
    )


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
    sources: list[str] = Field(
        default_factory=list, description="답변 본문과 분리된, 화면에 수정 불가 요소로 그대로 보여줄 출처 라벨 목록"
    )
    status: str
    cache_hit: Optional[bool] = None
    trace_url: Optional[str] = Field(
        default=None, description="이 처리 과정의 Langfuse 트레이스 링크 (담당자 디버깅용)"
    )
