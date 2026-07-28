"""민원·문의 입력 -> 답변 확인용 최소 Streamlit 화면.

백엔드(POST /inquiries)가 떠 있어야 한다:
    cd backend
    uvicorn app.main:app --reload

실행:
    cd frontend
    streamlit run app.py
"""
import requests
import streamlit as st

API_URL = "http://localhost:8000/inquiries"

st.set_page_config(page_title="CivicFlow Agent", page_icon="📮")
st.title("CivicFlow Agent — 민원·문의")

text = st.text_area("문의 내용을 입력하세요", placeholder="예: 반품하면 언제 환불되나요?", height=120)

if st.button("문의하기", type="primary") and text.strip():
    with st.spinner("처리 중..."):
        try:
            response = requests.post(API_URL, json={"text": text}, timeout=60)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as error:
            st.error(f"요청 실패: {error}")
        else:
            relevance = data.get("relevance_check") or {}
            classification = data.get("classification") or {}
            candidate_departments = (data.get("rule_flags") or {}).get("candidate_departments", [])

            st.markdown("### 처리 과정")
            st.write(f"**사용자 입력**: {data.get('raw_text')}")
            st.write(f"**관련여부**: {relevance.get('관련여부')}")
            st.write(f"**관련여부 판단 이유**: {relevance.get('판단근거')}")

            if classification:
                st.write(f"**문의 유형**: {classification.get('문의유형')}")
                st.write(
                    "**담당부서 후보**: "
                    + (", ".join(candidate_departments) if candidate_departments else "(없음)")
                )
                st.write(f"**최종 선정 담당부서**: {classification.get('담당부서')}")
                st.write(f"**우선순위**: {classification.get('우선순위')}")

            st.divider()
            st.markdown("### 답변")
            answer = data.get("draft_answer") or data.get("intake_reply") or "(답변이 생성되지 않았습니다.)"
            st.markdown(answer)
            st.caption(f"상태: {data.get('status')}")
