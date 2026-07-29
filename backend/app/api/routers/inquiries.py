import uuid

import psycopg2
from fastapi import APIRouter, HTTPException
from langfuse import propagate_attributes

from app.api.routers.submissions import _COLUMNS, _row_to_submission
from app.core.config import get_settings
from app.core.tracing import get_langfuse_client, get_langfuse_handler
from app.graph.build import get_compiled_graph
from app.graph.nodes.generate import build_draft_answer, generate_node
from app.graph.nodes.retrieve import retrieve_node
from app.models.schemas import (
    InquiryRequest,
    InquiryResponse,
    RegenerateAnswerRequest,
    RegenerateAnswerResponse,
)

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


def _fetch_submission(submission_id: str) -> dict:
    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_COLUMNS} FROM citizen_submissions WHERE id = %s", (submission_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="submission not found")
    return _row_to_submission(row)


def _process_from_submission(inquiry_id: str, submission_id: str) -> dict:
    """문의 접수함에서 'AI 처리'로 넘어온 건을 처리한다.

    intake(관련성 판별)와 classify_node+rules_node(문의유형/담당부서/우선순위/감정상태/
    핵심요청/분류근거/규칙 매칭 경로 분류)는 사용자가 /submit으로 접수한 시점에 이미
    한 번 실행되어 citizen_submissions에 저장돼 있다 — 이미 검증된 결과를 LLM으로 다시
    판단시키는 대신 그 값을 그대로 가져와 담당자에게 "확인차" 보여주고, 아직 하지 않은
    RAG 근거 검색 + 답변 초안 생성만 수행한다. core_request/classification_reason/
    matched_rules가 없는(이 기능 도입 이전에 접수된) 오래된 건은 안내문/빈 배열로 대신한다.
    """
    submission = _fetch_submission(submission_id)

    classification = {
        "문의유형": submission.inquiry_type,
        "문의유형들": submission.inquiry_types,
        "핵심요청": submission.core_request or submission.raw_text,
        "감정상태": submission.emotion,
        "우선순위": submission.priority,
        "담당부서": submission.department,
        "분류근거": submission.classification_reason
        or "사용자용 문의 접수 페이지에서 접수 시점에 이미 자동 분류된 결과입니다.",
    }
    rule_flags = {
        "matched_rules": submission.matched_rules,
        "candidate_departments": submission.candidate_departments,
        "requires_manager_review": submission.requires_manager_review,
        "review_reasons": [],
    }

    state = {
        "inquiry_id": inquiry_id,
        "raw_text": submission.raw_text,
        "classification": classification,
        "rule_flags": rule_flags,
    }
    state.update(retrieve_node(state))
    state.update(generate_node(state))
    return state


@router.post("", response_model=InquiryResponse)
def create_inquiry(payload: InquiryRequest) -> InquiryResponse:
    """문의 접수 -> LangGraph 파이프라인 실행 -> 담당자 검토용 결과 반환.

    전체 실행을 하나의 Langfuse 트레이스로 묶는다: 루트 span의 input은 원문 문의
    (내부 state 전체가 아니라)만 노출하고, tags는 하위의 모든 노드·LLM 호출·RAG
    검색 span에 자동 전파된다.

    session_id는 쓰지 않는다: 이 API는 대화형이 아니라 단건 요청-응답이라 "같은
    세션으로 묶일 다른 트레이스"가 애초에 없다. 대신 inquiry_id는 우리 DB
    (db/schema.sql의 inquiries.id)와 대조할 수 있도록 metadata로만 남긴다.
    """
    langfuse = get_langfuse_client()
    inquiry_id = str(uuid.uuid4())

    with langfuse.start_as_current_observation(
        name="process-inquiry",
        as_type="span",
        input={"raw_text": payload.text},
    ) as root_span:
        with propagate_attributes(
            metadata={"inquiry_id": inquiry_id},
            tags=["civicflow-agent", "inquiry-pipeline"],
            trace_name="process-inquiry",
        ):
            if payload.submission_id:
                final_state = _process_from_submission(inquiry_id, payload.submission_id)
            else:
                final_state = get_compiled_graph().invoke(
                    {
                        "inquiry_id": inquiry_id,
                        "raw_text": payload.text,
                        "skip_relevance_check": payload.skip_relevance_check,
                    },
                    config={"callbacks": [get_langfuse_handler()]},
                )

        root_span.update(
            output={
                "status": final_state.get("status"),
                "classification": final_state.get("classification"),
            }
        )
        # get_trace_url()은 프로젝트 ID 조회를 위해 Langfuse API를 실제로 호출한다.
        # 키 미설정/네트워크 장애 시 401 등으로 예외가 나더라도 트레이싱은 어디까지나
        # 부가 기능이므로 본 응답(문의 처리 결과)이 실패해서는 안 된다.
        try:
            trace_url = langfuse.get_trace_url()
        except Exception:
            trace_url = None

    # 데모/개발 단계에서는 요청 직후 traces가 바로 보이도록 즉시 flush 한다.
    # 트래픽이 커지면 SDK의 백그라운드 배치 전송에 맡기고 이 호출은 제거해도 된다.
    langfuse.flush()

    return InquiryResponse(**final_state, trace_url=trace_url)


@router.post("/regenerate-answer", response_model=RegenerateAnswerResponse)
def regenerate_answer(payload: RegenerateAnswerRequest) -> RegenerateAnswerResponse:
    """담당자가 RAG 검색 결과 화면에서 문서(1개 또는 여러 개)를 직접 골라 답변 초안을
    다시 만든다. intake/classify/apply_rules/retrieve는 이미 끝난 뒤라 다시 돌 필요가
    없어서, generate 단계만 다시 실행한다(전체 파이프라인 재실행 대비 훨씬 빠르다)."""
    draft_answer, sources = build_draft_answer(
        payload.raw_text,
        payload.classification,
        [doc.model_dump() for doc in payload.docs],
    )
    return RegenerateAnswerResponse(draft_answer=draft_answer, sources=sources)