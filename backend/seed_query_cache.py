"""query_cache 초기 시드용 스크립트.

사용법:
    python seed_query_cache.py run <부서>      # 파이프라인 실행 + 결과를 JSON으로 저장, 요약 출력
    python seed_query_cache.py commit <부서>   # run으로 저장된 JSON을 읽어 query_cache에 실제 반영

run과 commit을 분리한 이유: run은 실제 LLM을 호출하므로, 사용자가 결과를 확인하고
승인한 뒤에만 commit이 캐시에 반영되게 하기 위함이다 (commit은 LLM을 다시 호출하지
않고 run이 저장해둔 결과를 그대로 사용한다).
"""

import json
import sys
from pathlib import Path

RUNS_DIR = Path(sys.argv[0]).resolve().parent / "_cache_seed_runs"

SEED_QUESTIONS = {
    "IT지원팀": [
        "로그인이 계속 안 되는데 어떻게 해야 하나요?",
        "로그인 시 '아이디 또는 비밀번호가 일치하지 않습니다' 라는 오류가 계속 떠요.",
        "여러 번 로그인 실패했더니 로그인이 제한됐다고 나옵니다.",
        "자동 로그인이 풀려서 매번 다시 로그인해야 해요.",
        "로그인 버튼을 눌러도 아무 반응이 없어요.",
        "간편 로그인(카카오/네이버) 버튼을 눌렀는데 화면이 멈춰요.",
        "로그인 시 서버 오류 메시지가 뜹니다.",
        "비밀번호를 변경했는데도 예전 비밀번호로 로그인이 됩니다.",
        "계속 로그인이 안 되는데 어떻게 해결하나요?",
        "아이디로 로그인을 시도해도 계속 실패해요.",
    ],
    "정산팀": [
        "[환불] 반품 신청을 했는데, 언제 환불되나요?",
        "[환불] 휴대폰결제 후 취소했는데, 언제 환불되나요?",
        "[취소] 신용카드로 결제한 주문을 취소했는데 카드대금이 청구되었습니다.",
        "[환불] 다른 사람 명의의 계좌로 환불받을 수 있나요?",
        "[무통장 입금] 무통장입금 후 주문을 취소했는데 언제 환불되나요?",
        "[환불] 쿠팡캐시로 결제 후 주문을 취소했는데, 언제 환불되나요?",
        "[환불] 신용카드로 결제했는데, 다른 방법으로 환불받을 수 있나요?",
        "[환불] 주문을 취소했는데, 언제 환불되나요?",
        "주문을 취소했는데 환불은 언제쯤 받을 수 있나요?",
        "주문 취소했는데 환불이 왜 이렇게 오래 걸리나요?",
    ],
    "물류팀": [
        "[배송완료미수령] 상품을 받지 못했는데 배송완료로 확인됩니다.",
        "[상품누락] 상품을 구매했는데 일부만 배송되었어요.",
        "[배송일정] 배송조회를 했는데 배송정보가 없다고 나와요.",
        "[배송일정] 주문한 상품은 언제 배송되나요?",
        "[배송] 주문한 상품과 다른 상품이 배송되었어요.",
        "[배송] 배송 상태가 멈춰 있어요.",
        "[로켓직구] 주문한 상품 중 일부가 배송되지 않았어요.",
        "[배송일정] 배송상태가 계속 상품 준비 중입니다.",
        "제가 주문한 상품은 배송이 언제쯤 오나요?",
        "배송이 왜 이렇게 늦게 오나요?",
    ],
    "행정팀": [
        "휴학 신청은 어떻게 하나요?",
        "전과 신청은 어떻게 하나요?",
        "군휴학은 어떻게 신청하나요?",
        "교환학생 신청은 어떻게 진행하나요?",
        "기숙사 신청은 어떻게 하나요?",
        "자퇴 신청은 어떻게 진행하나요?",
        "휴학 신청 기간이 지났는데 신청할 수 있는 방법이 있나요?",
        "졸업유예 신청은 어떻게 하나요?",
        "휴학하려면 어떤 절차를 밟아야 하나요?",
        "휴학 신청 방법을 알고 싶어요.",
    ],
    "회원관리팀": [
        "[개인정보 설정] 개인정보 열람/정정 요청은 어떻게 할 수 있나요?",
        "[가입/탈퇴] 회원 탈퇴는 어떻게 하나요?",
        "회원정보 수정은 어떻게 하나요?",
        "가입 국가를 대만으로 변경하고 싶어요.",
        "[가입/탈퇴] 인증된 아이디가 이미 존재한다고 나옵니다.",
        "휴대폰 알림 설정을 변경하고 싶어요.",
        "라이브 방송에 노출되는 닉네임을 변경하고 싶어요.",
        "[가입/탈퇴] 쿠팡플레이의 탈퇴/해지는 어떻게 하나요?",
        "탈퇴하려면 어떻게 해야 하나요?",
        "회원 탈퇴를 하고 싶은데 어떻게 진행하나요?",
    ],
    "마케팅팀": [
        "여름 이벤트 쿠폰은 언제까지 사용 가능한가요?",
        "다운로드한 쿠폰의 유효기간이 얼마나 남았는지 확인하고 싶어요.",
        "프로모션 종료 후에도 이미 받은 쿠폰은 계속 쓸 수 있나요?",
        "생일 축하 쿠폰을 받았는데 언제까지 쓸 수 있나요?",
        "제가 가지고 있는 쿠폰 목록을 한 번에 확인할 수 있는 방법이 있나요?",
        "쿠폰 발급 수량이 소진되었다고 나오는데 다시 풀리는 시간이 있나요?",
        "이벤트 쿠폰이 언제 소멸되는지 알림을 받을 수 있나요?",
        "다른 사람에게 받은 쿠폰도 유효기간이 있나요?",
        "여름 이벤트 쿠폰 사용기한이 어떻게 되나요?",
        "이번 여름 쿠폰은 언제까지 쓸 수 있어요?",
    ],
    "법무팀": [
        "약관 위반으로 서비스 이용이 제한됐는데 이의를 제기할 수 있나요?",
        "약관 위반으로 서비스가 제한됐는데 이의를 제기할 수 있나요?",
        "계약서(약관)에 위약금 조항이 너무 과도하게 설정되어 있는데 그대로 적용되나요?",
        "약관에 있는 위약금 조항이 너무 과도한데 그대로 적용되나요?",
        "약관에 있는 면책조항이 부당하다고 생각되는데 어떻게 하나요?",
        "약관에 있는 면책조항 내용이 너무 부당한 것 같아요.",
        "약관에 있는 손해배상 제한 조항이 부당하다고 생각되는데 어떻게 하나요?",
        "손해배상 제한 조항이 너무 부당한 것 같아요.",
        "약관에 있는 면책조항이 부당한데 어떻게 해야 하나요?",
        "손해배상 책임 제한이 너무 과도한 것 같아요.",
    ],
}


def _run_pipeline_without_cache(inquiry_id: str, raw_text: str) -> dict:
    """check_cache/store_cache를 건너뛰고 intake~generate만 수동으로 이어붙여 실행한다.

    이 스크립트로 시딩을 검토하는 동안에는 query_cache가 아직 텅 비어있거나 검토 전
    상태여야 하는데, get_compiled_graph()를 그대로 쓰면 그래프에 붙어있는
    check_cache/store_cache가 검토용 실행 결과까지 캐시에 자동 저장해버리고, 이후
    비슷한 문구를 재시도할 때 새로 분류되는 대신 그 캐시를 히트해버려 검토 자체가
    무의미해진다. 그래서 시딩 스크립트는 이 저수준 체인으로 완전히 우회한다.
    """
    from app.graph.nodes.classify import classify_node
    from app.graph.nodes.generate import generate_node
    from app.graph.nodes.intake import intake_node
    from app.graph.nodes.intake_reply import greet_node, reject_node
    from app.graph.nodes.retrieve import retrieve_node
    from app.graph.nodes.rules import rules_node

    state = {"inquiry_id": inquiry_id, "raw_text": raw_text}
    state.update(intake_node(state))
    if not state.get("relevance_check", {}).get("관련여부", True):
        state.update(reject_node(state))
        return state

    state.update(greet_node(state))
    state.update(classify_node(state))
    state.update(rules_node(state))
    state.update(retrieve_node(state))
    state.update(generate_node(state))
    return state


def run(dept: str) -> None:
    questions = SEED_QUESTIONS[dept]
    results = []
    for i, text in enumerate(questions):
        inquiry_id = f"seed-{dept}-{i}"
        state = _run_pipeline_without_cache(inquiry_id, text)
        results.append({"inquiry_id": inquiry_id, "raw_text": text, "state": state})
        c = state.get("classification", {})
        rf = state.get("rule_flags", {})
        print(f"[{i + 1}/{len(questions)}] {text}")
        print(
            f"    문의유형={c.get('문의유형')} 담당부서={c.get('담당부서')} "
            f"우선순위={c.get('우선순위')} 관리자검토필요={rf.get('requires_manager_review')}"
        )
        answer = (state.get("draft_answer") or "").split("\n")[0]
        print(f"    답변 첫 줄: {answer[:70]}")

    RUNS_DIR.mkdir(exist_ok=True)
    out_path = RUNS_DIR / f"{dept}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(results)}건 실행 완료 → {out_path}")


def commit(dept: str) -> None:
    from app.rag.query_cache import store_cache_entry

    path = RUNS_DIR / f"{dept}.json"
    results = json.loads(path.read_text(encoding="utf-8"))

    stored, skipped = 0, 0
    for r in results:
        ok = store_cache_entry(r["inquiry_id"], r["raw_text"], r["state"])
        if ok:
            stored += 1
        else:
            skipped += 1
            print(f"  건너뜀(관리자검토필요): {r['raw_text']}")

    print(f"{dept}: {stored}건 저장, {skipped}건 건너뜀 (query_cache 컬렉션)")


if __name__ == "__main__":
    action, dept = sys.argv[1], sys.argv[2]
    if action == "run":
        run(dept)
    elif action == "commit":
        commit(dept)
    else:
        raise SystemExit(f"unknown action: {action}")
