from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.classify import classify_node
from app.graph.nodes.generate import generate_node
from app.graph.nodes.intake import intake_node
from app.graph.nodes.intake_reply import greet_node, reject_node
from app.graph.nodes.retrieve import retrieve_node
from app.graph.nodes.rules import rules_node
from app.graph.state import InquiryState


def _route_after_intake(state: InquiryState) -> str:
    """intake에서 관련 없는 입력으로 판별되면 분류/생성 없이 재질문 요청만 하고 끝낸다."""
    if not state.get("relevance_check", {}).get("관련여부", True):
        return "reject"
    return "greet"


@lru_cache
def get_compiled_graph():
    """4절 전체 시스템 흐름을 노드 단위로 그대로 옮긴 StateGraph.

    문의접수 -+-> (관련없음) 재질문 요청 -> END
              +-> 환영+요약 -> LLM유형분류 -> Rule보정(우선순위/담당부서) -> RAG근거검색 -> 답변초안생성 -> END

    민감 민원(9절 Rule)이어도 RAG 검색 + 답변 초안 생성은 다른 문의와 똑같이 실행된다
    — generate_node를 건너뛰고 정적 안내문으로 대체하던 manager_review 분기는 제거했다.
    '관리자 검토가 필요하다'는 신호 자체는 이 분기와 무관하게 apply_rules가 채우는
    rule_flags.requires_manager_review/review_reasons로 계속 전달되므로, 화면에서
    이 문의를 우선 검토 대상으로 표시하는 데는 지장이 없다.
    """
    graph = StateGraph(InquiryState)

    graph.add_node("intake", intake_node)
    graph.add_node("reject", reject_node)
    graph.add_node("greet", greet_node)
    graph.add_node("classify", classify_node)
    graph.add_node("apply_rules", rules_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges(
        "intake",
        _route_after_intake,
        {"reject": "reject", "greet": "greet"},
    )
    graph.add_edge("reject", END)
    graph.add_edge("greet", "classify")
    graph.add_edge("classify", "apply_rules")
    graph.add_edge("apply_rules", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()
