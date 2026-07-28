from app.core.tracing import get_langfuse_client
from app.graph.state import InquiryState
from app.rag.query_cache import lookup_cache_entry, store_cache_entry


def check_cache_node(state: InquiryState) -> dict:
    """그래프 맨 앞에서 실행되는 캐시 조회 노드.

    query_cache에서 유사한 과거 문의를 찾으면 그 결과를 그대로 재사용하고
    (cache_hit=True) intake~generate를 전부 건너뛰며, 없거나 유사도가 낮으면
    cache_hit=False만 남기고 기존 파이프라인으로 넘어간다. 실제 분기는
    build.py의 _route_after_cache가 담당한다.
    """
    raw_text = state["raw_text"].strip()

    with get_langfuse_client().start_as_current_observation(
        name="check-cache",
        as_type="retriever",
        input=raw_text,
    ) as span:
        cached = lookup_cache_entry(raw_text)
        span.update(output=cached)

    if cached is None:
        return {"cache_hit": False}

    return {
        "cache_hit": True,
        "classification": cached["classification"],
        "rule_flags": cached["rule_flags"],
        "retrieved_docs": cached["retrieved_docs"],
        "draft_answer": cached["draft_answer"],
        "sources": cached["sources"],
        "status": "pending_review",
    }


def store_cache_node(state: InquiryState) -> dict:
    """파이프라인을 끝까지 돈(캐시 MISS였던) 결과를 query_cache에 저장한다.

    저장 여부(관리자검토필요면 건너뜀)는 store_cache_entry가 판단하며,
    이 노드는 부수효과만 수행하고 상태를 바꾸지 않는다.
    """
    store_cache_entry(state["inquiry_id"], state["raw_text"], state)
    return {}
