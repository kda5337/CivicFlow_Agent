# -*- coding: utf-8 -*-
"""eval/metrics.py의 목표 지표(TARGETS)를 실제로 측정하기 위한 보조 설정.

여기 있는 두 값은 "실측"이 아니라 "가정"이다 — 코드가 계산해줄 수 없는 부분을
명시적인 상수로 남겨서, 나중에 실제 데이터로 교체할 지점을 분명히 표시한다.
"""

# 담당부서 -> 그 부서가 근거로 삼는 Supabase FAQ 테이블(들). RAG 검색 적합도를 측정할
# 때 "검색된 문서가 이 문의와 진짜 관련 있는가"를 사람이 일일이 라벨링하는 대신,
# "기대 담당부서의 FAQ 테이블에서 나온 문서인가"로 근사한다 — 완벽한 대체재는 아니지만
# 매 실행마다 재현 가능하고 코드로 검증 가능한 프록시다. backend/app/rag/knowledge_base.py
# 의 FAQ_SOURCES와 rules.yaml의 data_source 주석을 근거로 매핑했다.
DEPARTMENT_TO_SOURCE_TABLES = {
    "IT지원팀": {"it_support_faq"},
    "정산팀": {"coupang_faq"},
    "물류팀": {"coupang_faq_delivery"},
    "행정팀": {"admin_team_faq"},
    "회원관리팀": {"coupang_faq_personal_info", "duty_free_faq"},
    "법무팀": {"legal_team_faq"},
    "안전관리팀": {"safety_team_faq"},
    "마케팅팀": {"marketing_promotion_faq"},
    "고객지원총괄팀": {"sensitive_complaint_faq"},
    "고객센터": {"duty_free_faq", "coupang_faq_order_payment", "coupang_faq"},
}

# "수작업 대비 처리시간 단축률" 계산의 분모(초). 담당자가 문의 하나를 직접 검색·분류·
# 답변 작성까지 처리할 때 걸리는 평균 시간 — 조직마다 다르므로 실제 타임스터디 없이는
# 정확할 수 없는 가정값이다. 여기서는 보수적으로 3분(180초)을 뒀다. 실제 담당자 처리
# 시간을 측정할 수 있게 되면 이 값만 바꾸면 된다.
MANUAL_BASELINE_SECONDS = 180
