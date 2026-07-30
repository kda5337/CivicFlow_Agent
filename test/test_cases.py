# -*- coding: utf-8 -*-
"""부서 배정(rules_node) + 문의유형 분류(classify_node) 정밀도 측정용 테스트 케이스.

10개 담당부서 x 5건 = 50건. 각 케이스는 rules.yaml의 담당부서별 keywords(아래 주석 참고)를
자연스러운 민원·문의 문장에 녹여 작성했다 — "부서 배정이 맞는지"뿐 아니라 "LLM이 그 문장을
보고 실제로 어떤 문의유형으로 분류하는지"까지 함께 검증하기 위해 expected_inquiry_type도
같이 둔다.

담당부서별 rules.yaml 키워드(참고):
  IT지원팀        로그인/접속불가/오류/서버/먹통/안 열림
  정산팀          환불/취소/반품/결제오류/이중결제/과오납
  물류팀          배송/택배/미수령/파손/오배송
  행정팀          신청/등록/발급/서류/접수
  회원관리팀       회원가입/탈퇴/비밀번호/개인정보/아이디
  법무팀          소송/고발/약관/법적조치/손해배상/고소
  안전관리팀       사고/부상/화재/위험/안전
  마케팅팀        이벤트/쿠폰/할인/프로모션/광고
  고객지원총괄팀   (위 키워드에 안 걸리는 일반 불만/신고 — fallback)
  고객센터        (위 키워드에 안 걸리는 일반 안내/조회 — fallback)
"""

TEST_CASES = [
    # ── IT지원팀 (오류/장애) ──
    {"id": "IT-01", "expected_department": "IT지원팀", "expected_inquiry_type": "오류/장애",
     "text": "며칠 전부터 로그인이 계속 안 됩니다. 비밀번호는 맞는데 서버 오류라고만 떠요."},
    {"id": "IT-02", "expected_department": "IT지원팀", "expected_inquiry_type": "오류/장애",
     "text": "앱이 갑자기 먹통이 돼서 아무것도 안 눌립니다. 재설치해도 그대로예요."},
    {"id": "IT-03", "expected_department": "IT지원팀", "expected_inquiry_type": "오류/장애",
     "text": "사이트가 안 열려요. 오늘 하루 종일 접속 자체가 안 됩니다."},
    {"id": "IT-04", "expected_department": "IT지원팀", "expected_inquiry_type": "오류/장애",
     "text": "인증번호 받는 화면에서 서버 오류 메시지만 뜨고 다음 단계로 안 넘어갑니다."},
    {"id": "IT-05", "expected_department": "IT지원팀", "expected_inquiry_type": "오류/장애",
     "text": "결제 페이지에 들어가면 접속불가 오류가 뜹니다. 언제쯤 복구되나요?"},

    # ── 정산팀 (취소/환불) ──
    {"id": "PAY-01", "expected_department": "정산팀", "expected_inquiry_type": "취소/환불",
     "text": "주문을 취소했는데 환불이 아직 안 됐습니다. 확인 부탁드려요."},
    {"id": "PAY-02", "expected_department": "정산팀", "expected_inquiry_type": "취소/환불",
     "text": "결제가 실수로 두 번 됐어요. 이중결제된 금액 취소해 주세요."},
    {"id": "PAY-03", "expected_department": "정산팀", "expected_inquiry_type": "취소/환불",
     "text": "반품 신청한 지 일주일이 지났는데 환불 처리가 하나도 안 됩니다."},
    {"id": "PAY-04", "expected_department": "정산팀", "expected_inquiry_type": "취소/환불",
     "text": "결제 오류로 실제 금액보다 더 많이 청구됐어요. 과오납된 부분 환불 요청합니다."},
    {"id": "PAY-05", "expected_department": "정산팀", "expected_inquiry_type": "취소/환불",
     "text": "쿠폰 할인이 적용 안 된 채로 결제됐어요. 차액만큼 환불해 주실 수 있나요?"},

    # ── 물류팀 (오류/장애 — 배송 지연/파손) ──
    {"id": "LOG-01", "expected_department": "물류팀", "expected_inquiry_type": "오류/장애",
     "text": "배송이 3일째 그대로 멈춰 있습니다. 무슨 일이 있는 건가요?"},
    {"id": "LOG-02", "expected_department": "물류팀", "expected_inquiry_type": "오류/장애",
     "text": "택배를 받은 적이 없는데 배송완료로 떠 있어요."},
    {"id": "LOG-03", "expected_department": "물류팀", "expected_inquiry_type": "오류/장애",
     "text": "상품이 박스째 찌그러지고 파손된 상태로 도착했습니다."},
    {"id": "LOG-04", "expected_department": "물류팀", "expected_inquiry_type": "오류/장애",
     "text": "다른 사람 주소로 오배송된 것 같아요. 확인 부탁드립니다."},
    {"id": "LOG-05", "expected_department": "물류팀", "expected_inquiry_type": "오류/장애",
     "text": "배송 조회가 이틀째 업데이트가 안 되고 그대로예요."},

    # ── 행정팀 (신청/등록) ──
    {"id": "ADM-01", "expected_department": "행정팀", "expected_inquiry_type": "신청/등록",
     "text": "서류 발급을 신청했는데 처리 상태를 확인할 수가 없습니다."},
    {"id": "ADM-02", "expected_department": "행정팀", "expected_inquiry_type": "신청/등록",
     "text": "등록 신청서를 제출했는데 접수가 됐는지 확인이 안 됩니다."},
    {"id": "ADM-03", "expected_department": "행정팀", "expected_inquiry_type": "신청/등록",
     "text": "증빙서류를 첨부해서 신청했는데 반려 사유를 알려주지 않았습니다."},
    {"id": "ADM-04", "expected_department": "행정팀", "expected_inquiry_type": "신청/등록",
     "text": "온라인 신청이 계속 오류가 나서 접수 자체가 안 됩니다."},
    {"id": "ADM-05", "expected_department": "행정팀", "expected_inquiry_type": "신청/등록",
     "text": "발급 신청한 서류가 열흘이 지나도 도착하지 않았습니다."},

    # ── 회원관리팀 (변경/정정) ──
    {"id": "MEM-01", "expected_department": "회원관리팀", "expected_inquiry_type": "변경/정정",
     "text": "비밀번호를 변경하려는데 인증 메일이 오지 않습니다."},
    {"id": "MEM-02", "expected_department": "회원관리팀", "expected_inquiry_type": "변경/정정",
     "text": "회원 탈퇴를 신청했는데 아직도 로그인이 됩니다."},
    {"id": "MEM-03", "expected_department": "회원관리팀", "expected_inquiry_type": "변경/정정",
     "text": "개인정보 수정 요청을 했는데 며칠째 반영이 안 되고 있어요."},
    {"id": "MEM-04", "expected_department": "회원관리팀", "expected_inquiry_type": "변경/정정",
     "text": "아이디를 잊어버렸는데 찾기 기능도 작동하지 않습니다."},
    {"id": "MEM-05", "expected_department": "회원관리팀", "expected_inquiry_type": "변경/정정",
     "text": "휴대폰 번호를 변경했는데 계정 정보에는 그대로 옛날 번호가 남아 있어요."},

    # ── 법무팀 (불만/신고 — 소송/법적조치) ──
    {"id": "LEG-01", "expected_department": "법무팀", "expected_inquiry_type": "불만/신고",
     "text": "약관에 없는 방식으로 요금이 청구돼서 법적조치를 검토하고 있습니다."},
    {"id": "LEG-02", "expected_department": "법무팀", "expected_inquiry_type": "불만/신고",
     "text": "허위 광고로 피해를 입어서 손해배상을 청구하고 싶습니다."},
    {"id": "LEG-03", "expected_department": "법무팀", "expected_inquiry_type": "불만/신고",
     "text": "이 문제로 고소를 고려하고 있으니 담당자의 정확한 답변 부탁드립니다."},
    {"id": "LEG-04", "expected_department": "법무팀", "expected_inquiry_type": "불만/신고",
     "text": "계약 조건과 실제 서비스가 달라서 법적 대응을 준비 중입니다."},
    {"id": "LEG-05", "expected_department": "법무팀", "expected_inquiry_type": "불만/신고",
     "text": "이 건에 대해 소비자보호원에 신고하기 전에 먼저 사실 확인을 요청합니다."},

    # ── 안전관리팀 (불만/신고 — 사고/안전) ──
    {"id": "SAF-01", "expected_department": "안전관리팀", "expected_inquiry_type": "불만/신고",
     "text": "시설을 이용하다가 사고가 나서 부상을 입었습니다."},
    {"id": "SAF-02", "expected_department": "안전관리팀", "expected_inquiry_type": "불만/신고",
     "text": "화재 위험이 있어 보이는 시설을 발견해서 신고합니다."},
    {"id": "SAF-03", "expected_department": "안전관리팀", "expected_inquiry_type": "불만/신고",
     "text": "안전수칙이 전혀 지켜지지 않아 위험한 상황을 겪었습니다."},
    {"id": "SAF-04", "expected_department": "안전관리팀", "expected_inquiry_type": "불만/신고",
     "text": "이용 중 넘어져서 다쳤는데 안전 점검이 제대로 안 된 것 같습니다."},
    {"id": "SAF-05", "expected_department": "안전관리팀", "expected_inquiry_type": "불만/신고",
     "text": "위험물이 그대로 방치되어 있는 걸 봤습니다. 조치 부탁드립니다."},

    # ── 마케팅팀 (안내/조회 — 이벤트/쿠폰) ──
    {"id": "MKT-01", "expected_department": "마케팅팀", "expected_inquiry_type": "안내/조회",
     "text": "이번 이벤트 쿠폰이 적용이 안 되는데 사용 방법을 알고 싶습니다."},
    {"id": "MKT-02", "expected_department": "마케팅팀", "expected_inquiry_type": "안내/조회",
     "text": "프로모션 할인가가 결제 시 반영이 안 됐는데 어떻게 된 건가요?"},
    {"id": "MKT-03", "expected_department": "마케팅팀", "expected_inquiry_type": "안내/조회",
     "text": "쿠폰 유효기간이 언제까지인지 궁금합니다."},
    {"id": "MKT-04", "expected_department": "마케팅팀", "expected_inquiry_type": "안내/조회",
     "text": "이벤트 응모는 했는데 당첨 여부를 어디서 확인하나요?"},
    {"id": "MKT-05", "expected_department": "마케팅팀", "expected_inquiry_type": "안내/조회",
     "text": "광고에서 본 할인 프로모션이 지금도 진행 중인지 확인하고 싶습니다."},

    # ── 고객지원총괄팀 (불만/신고 — 일반 fallback) ──
    {"id": "CS-01", "expected_department": "고객지원총괄팀", "expected_inquiry_type": "불만/신고",
     "text": "여러 번 문의했는데 답변이 없어서 다시 남깁니다. 너무 불편합니다."},
    {"id": "CS-02", "expected_department": "고객지원총괄팀", "expected_inquiry_type": "불만/신고",
     "text": "상담원 응대가 너무 불친절해서 항의하고 싶습니다."},
    {"id": "CS-03", "expected_department": "고객지원총괄팀", "expected_inquiry_type": "불만/신고",
     "text": "같은 문제로 세 번째 문의드리는데 계속 해결이 안 됩니다."},
    {"id": "CS-04", "expected_department": "고객지원총괄팀", "expected_inquiry_type": "불만/신고",
     "text": "전반적인 서비스 품질에 실망해서 불만을 제기합니다."},
    {"id": "CS-05", "expected_department": "고객지원총괄팀", "expected_inquiry_type": "불만/신고",
     "text": "이전에 문의드린 건에 대한 후속 조치가 전혀 없었습니다."},

    # ── 고객센터 (안내/조회 — 일반 fallback) ──
    {"id": "GEN-01", "expected_department": "고객센터", "expected_inquiry_type": "안내/조회",
     "text": "이용 방법을 잘 몰라서 안내 부탁드립니다."},
    {"id": "GEN-02", "expected_department": "고객센터", "expected_inquiry_type": "안내/조회",
     "text": "결제 수단에는 어떤 것들이 있는지 궁금합니다."},
    {"id": "GEN-03", "expected_department": "고객센터", "expected_inquiry_type": "안내/조회",
     "text": "이용약관 내용을 조금 더 자세히 알고 싶습니다."},
    {"id": "GEN-04", "expected_department": "고객센터", "expected_inquiry_type": "안내/조회",
     "text": "적립금 사용 방법이 궁금해서 문의드립니다."},
    {"id": "GEN-05", "expected_department": "고객센터", "expected_inquiry_type": "안내/조회",
     "text": "고객센터 운영시간이 어떻게 되는지 알려주세요."},
]
