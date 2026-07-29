import uuid
from datetime import datetime, timezone

import psycopg2
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.graph.nodes.classify import classify_node
from app.graph.nodes.intake import check_relevance
from app.graph.nodes.rules import rules_node
from app.models.schemas import (
    CitizenSubmission,
    CitizenSubmissionRequest,
    SubmissionAnswerUpdate,
    SubmissionClassificationUpdate,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])

_COLUMNS = (
    "id, name, contact, raw_text, submitted_at, status, "
    "inquiry_type, inquiry_types, department, candidate_departments, priority, emotion, "
    "core_request, classification_reason, requires_manager_review, matched_rules, final_answer"
)


def _row_to_submission(row) -> CitizenSubmission:
    return CitizenSubmission(
        id=str(row[0]),
        name=row[1],
        contact=row[2],
        raw_text=row[3],
        submitted_at=row[4].isoformat(),
        status=row[5],
        inquiry_type=row[6],
        inquiry_types=row[7] or [],
        department=row[8],
        candidate_departments=row[9] or [],
        priority=row[10],
        emotion=row[11],
        core_request=row[12],
        classification_reason=row[13],
        requires_manager_review=row[14],
        matched_rules=row[15] or [],
        final_answer=row[16],
    )


@router.post("", response_model=CitizenSubmission)
def create_submission(payload: CitizenSubmissionRequest) -> CitizenSubmission:
    """사용자용 문의 접수 페이지에서 이름/연락처/문의 원문을 받아 저장한다.

    DB에 등록되기 전에 먼저 intake_node의 관련성 판별(check_relevance)을 거친다 —
    민원·문의가 아닌 내용(잡담/광고/무관한 질문 등)은 애초에 citizen_submissions에
    쌓이지 않도록 422로 거부한다. 관련성이 확인된 것만 classify_node+rules_node를
    바로 실행한다(RAG 검색·답변 생성은 하지 않음 — 담당자가 내부 화면에서 실제 답변까지
    만들 때 전체 파이프라인을 돈다). 이 결과가 사용자 페이지의 "문의 유형 자동 확인"에
    그대로 뜨고, status는 '검토중'이 된다.
    """
    text = payload.raw_text.strip()
    relevance = check_relevance(text)
    if not relevance.관련여부:
        raise HTTPException(status_code=422, detail=relevance.판단근거)

    settings = get_settings()
    submission_id = str(uuid.uuid4())
    submitted_at = datetime.now(timezone.utc)

    state = {"raw_text": text}
    state.update(classify_node(state))
    state.update(rules_node(state))
    classification = state["classification"]
    rule_flags = state["rule_flags"]

    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO citizen_submissions "
                "(id, name, contact, raw_text, submitted_at, status, "
                "inquiry_type, inquiry_types, department, candidate_departments, priority, emotion, "
                "core_request, classification_reason, requires_manager_review, matched_rules) "
                "VALUES (%s, %s, %s, %s, %s, '검토중', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    submission_id,
                    payload.name,
                    payload.contact,
                    text,
                    submitted_at,
                    classification["문의유형"],
                    classification.get("문의유형들", []),
                    classification["담당부서"],
                    rule_flags.get("candidate_departments", []),
                    classification["우선순위"],
                    classification.get("감정상태"),
                    classification.get("핵심요청"),
                    classification.get("분류근거"),
                    rule_flags.get("requires_manager_review", False),
                    rule_flags.get("matched_rules", []),
                ),
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_COLUMNS} FROM citizen_submissions WHERE id = %s", (submission_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    return _row_to_submission(row)


@router.get("", response_model=list[CitizenSubmission])
def list_submissions(name: str | None = None) -> list[CitizenSubmission]:
    """문의 목록 조회. 최신 제출 순으로 정렬한다.

    name을 안 주면(담당자용 문의 접수함) 전체를 돌려주고, name을 주면(사용자용 페이지가
    "내 문의 내역"/"처리 상태 조회"/"답변 확인"을 보여줄 때) 그 이름으로 남긴 것만
    필터링한다 — 로그인이 없는 구조라 이름만으로 구분하므로, 동명이인이 있으면 서로의
    내역이 함께 보일 수 있다.
    """
    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            if name:
                cur.execute(
                    f"SELECT {_COLUMNS} FROM citizen_submissions WHERE name = %s ORDER BY submitted_at DESC",
                    (name,),
                )
            else:
                cur.execute(f"SELECT {_COLUMNS} FROM citizen_submissions ORDER BY submitted_at DESC")
            rows = cur.fetchall()
    finally:
        conn.close()

    return [_row_to_submission(row) for row in rows]


@router.patch("/{submission_id}/classification", response_model=CitizenSubmission)
def update_classification(submission_id: str, payload: SubmissionClassificationUpdate) -> CitizenSubmission:
    """담당자가 '문의 접수함'에서 AI 처리(전체 파이프라인)를 실행한 뒤, 그 결과를
    원본 접수 건에 되돌려 기록한다 — 담당자가 담당부서를 직접 고쳤다면 그 값이 반영된다.
    status를 '검토중'으로 바꾼다(이미 접수 시점에 자동 분류가 한 번 됐어도, 전체
    파이프라인 결과로 갱신하는 것이 더 정확하다)."""
    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE citizen_submissions "
                "SET inquiry_type = %s, inquiry_types = %s, department = %s, "
                "candidate_departments = %s, priority = %s, emotion = %s, "
                "core_request = %s, classification_reason = %s, "
                "requires_manager_review = %s, status = '검토중' "
                "WHERE id = %s",
                (
                    payload.inquiry_type,
                    payload.inquiry_types,
                    payload.department,
                    payload.candidate_departments,
                    payload.priority,
                    payload.emotion,
                    payload.core_request,
                    payload.classification_reason,
                    payload.requires_manager_review,
                    submission_id,
                ),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="submission not found")
            conn.commit()
            cur.execute(f"SELECT {_COLUMNS} FROM citizen_submissions WHERE id = %s", (submission_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    return _row_to_submission(row)


@router.patch("/{submission_id}/answer", response_model=CitizenSubmission)
def update_answer(submission_id: str, payload: SubmissionAnswerUpdate) -> CitizenSubmission:
    """담당자가 답변 초안 화면에서 '최종 답변으로 저장'을 눌렀을 때 확정 답변을
    저장한다. status를 '답변완료'로 바꾼다."""
    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE citizen_submissions SET final_answer = %s, status = '답변완료' WHERE id = %s",
                (payload.final_answer, submission_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="submission not found")
            conn.commit()
            cur.execute(f"SELECT {_COLUMNS} FROM citizen_submissions WHERE id = %s", (submission_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    return _row_to_submission(row)
