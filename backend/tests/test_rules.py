"""rules_node는 LLM/DB 호출이 없는 순수 함수(rules.yaml 키워드 매칭)라, 실제 배포 전
빠르게 회귀를 잡을 수 있는 지점이다."""

from app.graph.nodes.rules import rules_node


def test_rules_node_routes_login_error_to_it_support():
    state = {
        "raw_text": "로그인이 계속 안 되고 서버 오류가 떠요.",
        "classification": {"주요문의유형": "오류/장애"},
    }
    result = rules_node(state)

    assert result["classification"]["담당부서"] == "IT지원팀"
    assert result["classification"]["우선순위"] == "보통"
    assert result["rule_flags"]["requires_manager_review"] is False


def test_rules_node_flags_safety_incidents_for_manager_review():
    state = {
        "raw_text": "매장에서 화재가 발생해서 다쳤어요.",
        "classification": {"주요문의유형": "불만/신고"},
    }
    result = rules_node(state)

    assert result["classification"]["담당부서"] == "안전관리팀"
    assert result["rule_flags"]["requires_manager_review"] is True


def test_rules_node_urgent_keyword_raises_priority():
    state = {
        "raw_text": "오늘 안에 긴급하게 처리해 주세요.",
        "classification": {"주요문의유형": "일반문의"},
    }
    result = rules_node(state)

    assert result["classification"]["우선순위"] == "높음"
