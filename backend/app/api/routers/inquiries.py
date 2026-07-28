import uuid

from fastapi import APIRouter
from langfuse import propagate_attributes

from app.core.tracing import get_langfuse_client, get_langfuse_handler
from app.graph.build import get_compiled_graph
from app.models.schemas import InquiryRequest, InquiryResponse

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


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
            final_state = get_compiled_graph().invoke(
                {"inquiry_id": inquiry_id, "raw_text": payload.text},
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