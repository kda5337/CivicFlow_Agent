"""intake_node, classify_node, curriculum_lookup_node 수동 테스트용 임시 스크립트. 완료 후 삭제해도 됨."""
from dotenv import load_dotenv

load_dotenv()

from app.graph.build import get_compiled_graph
from app.graph.nodes.classify import classify_node
from app.graph.nodes.intake import intake_node
from app.graph.nodes.intake_reply import greet_node, reject_node


def trace_graph(text: str) -> dict:
    """컴파일된 그래프를 실제로 실행해, 입력과 최종 생성 답변만 출력하고 최종 state를 반환한다.
    관련없음으로 거부된 입력은 draft_answer 대신 intake_reply(재질문 요청)를 보여준다."""
    graph = get_compiled_graph()
    state = {"inquiry_id": "trace", "raw_text": text}

    final_state = dict(state)
    for update in graph.stream(state, stream_mode="updates"):
        for node_output in update.values():
            final_state.update(node_output)

    answer = final_state.get("draft_answer") or final_state.get("intake_reply")
    print(f"입력: {text}")
    print(f"답변: {answer}")
    print()
    return final_state

state = {
    "inquiry_id": "test-1",
    "raw_text": "  수강신청을 했는데 신청 내역이 보이지 않습니다. 오늘 안에 처리해야 합니다. ",
}

print("=== intake_node (관련있는 입력) ===")
intake_result = intake_node(state)
print(intake_result)

state.update(intake_result)

print("\n=== greet_node ===")
greet_result = greet_node(state)
print(greet_result)

state.update(greet_result)

print("\n=== classify_node ===")
classify_result = classify_node(state)
print(classify_result)

print("\n\n=== intake_node (관련없는 입력) ===")
irrelevant_state = {
    "inquiry_id": "test-2",
    "raw_text": "오늘 저녁 뭐 먹을지 추천해줘",
}
irrelevant_intake_result = intake_node(irrelevant_state)
print(irrelevant_intake_result)

irrelevant_state.update(irrelevant_intake_result)

print("\n=== reject_node ===")
reject_result = reject_node(irrelevant_state)
print(reject_result)


print("\n\n=== 전체 그래프 노드별 트레이스 (intake -> ... -> generate) ===")
for text in [
    "반품하면 언제 환불되나요?",              # 취소환불_분류 -> chroma_merged_faq
    "면세 제품을 사려면, 뭐가 필요해?",  # 졸업요건_문의 -> curriculum_lookup
    "오늘 저녁 뭐 먹을지 추천해줘",            # 관련없음 -> reject
]:
    trace_graph(text)