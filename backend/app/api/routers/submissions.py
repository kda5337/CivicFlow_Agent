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
    RelevanceCheckResult,
    SubmissionAnswerUpdate,
    SubmissionCacheCheckRequest,
    SubmissionCacheCheckResponse,
    SubmissionClassificationUpdate,
    SubmissionRelevanceCheckRequest,
)
from app.rag.answer_cache import store_answer_cache_entry
from app.rag.query_cache import lookup_cache_entry

router = APIRouter(prefix="/submissions", tags=["submissions"])

# check_cache_node(그래프 경로)의 기본 임계값(0.80)보다 엄격하게 잡은, 시민 접수
# 경로 전용 재사용 기준. 잘못 재사용됐을 때 되돌리기가 더 번거로운 만큼 안전 마진을 둔다.
SUBMISSION_CACHE_SIMILARITY_THRESHOLD = 0.90

_COLUMNS = (
    "id, name, contact, raw_text, submitted_at, status, "
    "inquiry_type, inquiry_types, department, candidate_departments, priority, emotion, "
    "core_request, classification_reason, requires_manager_review, matched_rules, final_answer, "
    "from_cache, sources"
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
        from_cache=row[17],
        sources=row[18] or [],
    )


@router.post("/check-relevance", response_model=RelevanceCheckResult)
def check_submission_relevance(payload: SubmissionRelevanceCheckRequest) -> RelevanceCheckResult:
    """문의 등록 전, 관련성만 먼저 판별한다 — DB에는 아무것도 쓰지 않는다.

    프론트가 "작성" -> "적절성 확인 중" -> "분류 중" -> "접수 완료" 화면을 실제 백엔드
    진행 상황에 맞춰 순서대로 넘기기 위해 둔 엔드포인트다. 이 응답으로 "분류 중" 화면으로
    전환한 뒤, 곧바로 POST /submissions(skip_relevance_check=True)를 호출해 분류+저장을
    마친다. 관련성 판별은 결과가 결정적이지 않을 수 있어(같은 텍스트라도 LLM 호출마다
    미세하게 갈릴 수 있음) 뒤이은 호출에서 다시 판별하지 않고 이 결과를 그대로 신뢰한다.
    """
    return check_relevance(payload.raw_text.strip())


@router.post("/cache-check", response_model=SubmissionCacheCheckResponse)
def check_submission_cache(payload: SubmissionCacheCheckRequest) -> SubmissionCacheCheckResponse:
    """등록 전에 분류 캐시(query_cache) 히트 여부만 먼저 확인한다 — DB에는 아무것도 쓰지
    않는다. 프론트가 이 응답으로 실제 관련성 판별(check-relevance) 호출을 할지 말지
    정하지만, "적절성 확인 중" 화면 자체는 그대로 보여준다 — 캐시로 처리돼도 사용자에게는
    똑같이 접수가 진행되는 것으로 보이는 게 자연스럽기 때문이다. 다만 그 화면이 실제
    LLM 호출(수 초) 없이 짧은 연출용 지연만으로 넘어가게 된다."""
    cached = lookup_cache_entry(payload.raw_text.strip(), threshold=SUBMISSION_CACHE_SIMILARITY_THRESHOLD)
    return SubmissionCacheCheckResponse(cache_hit=cached is not None)


@router.post("", response_model=CitizenSubmission)
def create_submission(payload: CitizenSubmissionRequest) -> CitizenSubmission:
    """사용자용 문의 접수 페이지에서 이름/연락처/문의 원문을 받아 저장한다.

    먼저 query_cache에서 비슷한 과거 문의를 찾는다(check_cache_node의 기본 임계값
    0.80보다 더 엄격한 0.90 이상 유사할 때만 재사용 — 시민이 직접 접수하는 값은 잘못
    재사용됐을 때 되돌리기 더 번거로우므로 안전 마진을 더 둔다). 히트하면 관련성
    판별(check_relevance)과 classify_node+rules_node를 전부 건너뛰고 그 결과를 그대로
    쓴다 — 캐시 항목은 저장될 때 이미 관련성 검증을 통과한 것만 남으므로 다시 확인할
    필요가 없다. 못 찾으면(MISS), skip_relevance_check가 없을 때만 관련성 판별을
    거친다 — 민원·문의가 아닌 내용(잡담/광고/무관한 질문 등)은 애초에
    citizen_submissions에 쌓이지 않도록 422로 거부한다. (프론트가 POST
    /submissions/check-relevance로 이미 확인을 마친 뒤 넘어온 경우엔
    skip_relevance_check=True로 이 단계를 건너뛴다.) 그런 다음 classify_node+rules_node를
    직접 실행한다(RAG 검색·답변 생성은 하지 않음 — 담당자가 내부 화면에서 실제 답변까지
    만들 때 전체 파이프라인을 돈다). 이 결과가 사용자 페이지의 "문의 유형 자동 확인"에
    그대로 뜨고, status는 '검토중'이 된다. 캐시를 재사용했는지는 from_cache 컬럼에
    남겨, 나중에 담당자가 이 분류가 캐시 재사용인지 새 분류인지 구분할 수 있게 한다.
    """
    text = payload.raw_text.strip()

    cached = lookup_cache_entry(text, threshold=SUBMISSION_CACHE_SIMILARITY_THRESHOLD)

    if cached is None and not payload.skip_relevance_check:
        relevance = check_relevance(text)
        if not relevance.관련여부:
            raise HTTPException(status_code=422, detail=relevance.판단근거)

    from_cache = cached is not None
    if cached is not None:
        classification = cached["classification"]
        rule_flags = cached["rule_flags"]
    else:
        state = {"raw_text": text}
        state.update(classify_node(state))
        state.update(rules_node(state))
        classification = state["classification"]
        rule_flags = state["rule_flags"]

    settings = get_settings()
    submission_id = str(uuid.uuid4())
    submitted_at = datetime.now(timezone.utc)

    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO citizen_submissions "
                "(id, name, contact, raw_text, submitted_at, status, "
                "inquiry_type, inquiry_types, department, candidate_departments, priority, emotion, "
                "core_request, classification_reason, requires_manager_review, matched_rules, from_cache) "
                "VALUES (%s, %s, %s, %s, %s, '검토중', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
                    from_cache,
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
    저장한다. status를 '답변완료'로 바꾼다.

    저장이 끝나면 answer_cache에도 등록한다 — 이 문의와 비슷한 문의가 나중에 "AI 처리"로
    넘어오면(_process_from_submission), generate_node를 다시 돌리는 대신 지금 담당자가
    검토·승인한 이 답변을 그대로 재사용한다(민감 민원은 store_answer_cache_entry가
    알아서 건너뛴다)."""
    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE citizen_submissions SET final_answer = %s, sources = %s, status = '답변완료' WHERE id = %s",
                (payload.final_answer, payload.sources, submission_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="submission not found")
            conn.commit()
            cur.execute(f"SELECT {_COLUMNS} FROM citizen_submissions WHERE id = %s", (submission_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    submission = _row_to_submission(row)
    store_answer_cache_entry(
        raw_text=submission.raw_text,
        final_answer=submission.final_answer,
        sources=submission.sources,
        requires_manager_review=submission.requires_manager_review,
        submission_id=submission_id,
    )
    return submission
