"""intake -> classify -> apply_rules 파이프라인에서 의도(문의유형)가 어떻게 분류되고
담당부서/우선순위가 어떻게 결정되는지 확인하기 위한 수동 테스트 스크립트.

문의유형 7개 카테고리를 하나씩 대표하는 샘플 문장으로 실행한다. classify_node는
문의유형/핵심요청/감정상태만 판단하고(담당부서/우선순위는 없음), rules_node가
rules.yaml만으로 담당부서/우선순위를 처음부터 결정한다.
"""
from dotenv import load_dotenv

load_dotenv()

from app.graph.nodes.classify import classify_node
from app.graph.nodes.intake import intake_node
from app.graph.nodes.rules import rules_node

SAMPLE_INQUIRIES = [
    "신규 회원 등록을 신청하고 싶은데 어떻게 접수하나요?",          # 신청/등록 -> 행정팀
    "배송지 주소를 잘못 입력했는데 변경할 수 있을까요?",             # 변경/정정 -> 회원관리팀
    "결제한 상품을 반품하고 환불받고 싶어요.",                       # 취소/환불 -> 정산팀
    "로그인이 안 되고 자꾸 오류가 나서 오늘 안에 확인 부탁드려요.",   # 오류/장애 -> IT지원팀 (+우선순위 높음)
    "서비스 때문에 정말 큰 피해를 입어서 항의하려고 합니다.",         # 불만/신고 -> 고객지원총괄팀 (+관리자검토)
    "진행 중인 이벤트 쿠폰은 언제까지 쓸 수 있는지 궁금해요.",       # 안내/조회 -> 마케팅팀
    "그냥 궁금해서 문의드립니다. 운영시간이 어떻게 되나요?",         # 일반문의 -> 고객센터
    "지금 사고가 나서 응급으로 도움이 필요합니다!",                 # 오류/장애 -> 안전관리팀 + 우선순위 최상
    "오늘 저녁 뭐 먹을지 추천해줘",                                 # 관련없음 -> intake에서 reject
]


def run_pipeline(text: str) -> None:
    state = {"inquiry_id": "intent-test", "raw_text": text}

    intake_result = intake_node(state)
    state.update(intake_result)

    print(f"입력: {text}")
    relevance = intake_result["relevance_check"]
    print(f"  [intake] 관련여부={relevance['관련여부']} ({relevance['판단근거']})")

    if not relevance["관련여부"]:
        print("  -> 관련 없음으로 판별되어 classify/rules 단계를 실행하지 않음")
        print()
        return

    classify_result = classify_node(state)
    state.update(classify_result)
    before = classify_result["classification"]
    print(
        "  [classify]    "
        f"문의유형={before['문의유형']} / 감정상태={before['감정상태']} ")

    rules_result = rules_node(state)
    after = rules_result["classification"]
    flags = rules_result["rule_flags"]
    print(
        "  [rules 최종]  "
        f"문의유형={after['문의유형']} / 우선순위={after['우선순위']} / 담당부서={after['담당부서']}"
    )
    print(f"  matched_rules={flags['matched_rules']}")
    print(f"  candidate_departments={flags['candidate_departments']}")
    print(f"  requires_manager_review={flags['requires_manager_review']}")
    print()


if __name__ == "__main__":
    for text in SAMPLE_INQUIRIES:
        run_pipeline(text)
