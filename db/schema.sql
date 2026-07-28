-- PostgreSQL 스키마 (12절 기술스택: PostgreSQL/MySQL)

CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE inquiries (
    id UUID PRIMARY KEY,
    raw_text TEXT NOT NULL,
    inquiry_type TEXT,          -- 문의유형: 신청/변경/취소환불/오류장애/일반문의/긴급문의
    priority TEXT,               -- 우선순위: 낮음/보통/높음
    department_id INT REFERENCES departments(id),
    classification_reason TEXT,  -- 분류근거
    matched_rules TEXT[],
    candidate_departments TEXT[], -- 겹쳤던 담당부서 후보 전체 (priority로 department_id 하나가 최종 결정됨)
    status TEXT NOT NULL,        -- pending_review / urgent_manager_review / resolved
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE retrieved_evidence (
    id SERIAL PRIMARY KEY,
    inquiry_id UUID REFERENCES inquiries(id),
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    score FLOAT NOT NULL
);

CREATE TABLE answer_drafts (
    id SERIAL PRIMARY KEY,
    inquiry_id UUID REFERENCES inquiries(id) UNIQUE,
    draft_text TEXT,
    final_text TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ
);

-- 학번(cohort)별 졸업 이수학점 기준
CREATE TABLE graduation_requirements (
    id SERIAL PRIMARY KEY,
    cohort SMALLINT NOT NULL,          -- 입학년도 (22학번 -> 2022)
    category TEXT NOT NULL,             -- 기초교양/융합교양/계열교양/전공필수/전공선택/총졸업학점
    required_credits INT,               -- 계열교양 '-'처럼 미지정인 경우 NULL 허용
    UNIQUE (cohort, category)
);

-- 학번(cohort)별 교육과정 개별 교과목
CREATE TABLE curriculum_courses (
    id SERIAL PRIMARY KEY,
    requirement_id INT NOT NULL REFERENCES graduation_requirements(id),
    track TEXT,                         -- NULL=공통과정, 'Language-AI', 'Vision-AI'
    year SMALLINT NOT NULL,             -- 학년 (1~4)
    semester SMALLINT NOT NULL,         -- 학기 (1~2)
    course_name TEXT NOT NULL,
    credits SMALLINT NOT NULL,
    theory_hours SMALLINT NOT NULL,
    practice_hours SMALLINT NOT NULL
);

-- AI Hub 취소/반품/교환/환불/AS 상담 데이터 기반 FAQ.
-- question/answer 모두 LLM 가공 없이 consulting_content 원문에서 화자(고객/상담사)
-- 발화만 그대로 추출한 것이다. 질문(question)만 Chroma에 임베딩하고, 이 테이블의 id를
-- metadata.supabase_id로 남겨 검색된 질문에서 실제 답변(answer)을 다시 조회하는 구조로 쓴다.
CREATE TABLE cancel_refund_faq (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,               -- 액티벤처/엘지유플러스/하나카드
    source_id TEXT NOT NULL,            -- AI Hub 원본 상담 세션 ID
    consulting_category TEXT NOT NULL,
    question TEXT NOT NULL,             -- 원문에서 '고객:' 발화만 그대로 추출
    answer TEXT NOT NULL,               -- 원문에서 '상담사:' 발화만 그대로 추출
    UNIQUE (source, source_id)
);

-- data.go.kr 15118694(제주관광공사_온라인면세점 자주묻는 질문) 기반 FAQ.
-- 질문(question)만 Chroma(chroma_duty_free_faq)에 임베딩하고, 이 테이블의 id를
-- metadata.supabase_id로 남겨 검색된 질문에서 실제 답변(answer)을 다시 조회하는 구조로 쓴다.
CREATE TABLE duty_free_faq (
    id SERIAL PRIMARY KEY,
    faq_id INT NOT NULL UNIQUE,          -- 원본 자주묻는질문아이디
    faq_type TEXT,                        -- 자주묻는질문타입
    question TEXT NOT NULL,               -- 자주묻는질문제목
    answer TEXT NOT NULL,                 -- 자주묻는질문내용
    registered_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    source TEXT NOT NULL DEFAULT 'data.go.kr:15118694',
    source_dataset_id TEXT,               -- 공공데이터포털 데이터셋 번호, 예: "15118694"
    source_dataset_name TEXT,             -- 공식 데이터셋명, 예: "제주관광공사_온라인면세점 자주묻는 질문"
    source_faq_type_index INT             -- faq_type 안에서 몇 번째 질문인지 (1부터)
);

-- 쿠팡 뉴스룸 FAQ 원본 3종(환불/취소·교환·반품/이용정책)을 합친 질문-답변.
-- question만 Chroma(chroma_coupang_faq)에 임베딩하고, 이 테이블의 id를
-- metadata.supabase_id로 남겨 검색된 질문에서 실제 답변(answer)을 다시 조회하는 구조로 쓴다.
CREATE TABLE coupang_faq (
    id SERIAL PRIMARY KEY,
    faq_id INT NOT NULL UNIQUE,               -- coupang_faq_combined.json의 전역 id(1~65)
    category TEXT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source TEXT NOT NULL,                     -- 데이터셋 출처 라벨(예: "공식 쿠팡 정책")
    source_url TEXT,
    published_date TEXT,
    source_pdf_file TEXT,                     -- 원본 PDF 파일명 (업로드된 6개 PDF 중 하나, 없으면 NULL)
    source_pdf_question_number INT,           -- 그 PDF 안에서 몇 번째 질문인지 (없으면 NULL)
    source_pdf_note TEXT                       -- PDF에 없는 항목일 경우의 비고
);

-- 쿠팡 개인정보 FAQ(PDF 3편: ep_1~ep_3, 가입/탈퇴·개인정보 설정·인증·비밀번호 관리·
-- 로그인/로그아웃 카테고리). 회원관리팀 담당 문의(변경/정정, 계정 관련 오류/장애)의
-- RAG 근거로 쓴다. question만 Chroma(chroma_merged_faq)에 임베딩하고, 이 테이블의 id를
-- metadata.supabase_id로 남겨 검색된 질문에서 실제 답변(answer)을 다시 조회하는 구조로 쓴다.
-- coupang_faq와 컬럼 구성을 동일하게 맞춰(faq_id 제외) retrieve.py에서 로직을 재사용한다.
CREATE TABLE coupang_faq_personal_info (
    id SERIAL PRIMARY KEY,
    category TEXT,                             -- 질문 앞 대괄호에서 추출 (가입/탈퇴, 개인정보 설정 등)
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source TEXT NOT NULL,                       -- 데이터셋 출처 라벨(예: "공식 쿠팡 정책")
    source_url TEXT,                            -- 이 데이터셋은 전부 PDF 유래라 NULL
    source_pdf_file TEXT,                       -- 자주_묻는_질문_개인정보_ep_1.pdf 등
    source_pdf_question_number INT,             -- 그 PDF 안에서 몇 번째 질문인지
    source_pdf_note TEXT,                       -- 전부 PDF 유래라 항상 NULL(스키마 일관성을 위해 유지)
    UNIQUE (source_pdf_file, source_pdf_question_number)
);

-- 쿠팡 배송 FAQ(PDF 8편: ep_1~ep_8, 배송완료미수령·상품파손·오배송·배송지연·배송비·
-- 통관 등 카테고리). 물류팀 담당 문의(취소/환불, 안내/조회의 배송 관련)의 RAG 근거로
-- 쓴다. question만 Chroma(chroma_merged_faq)에 임베딩하고, 이 테이블의 id를
-- metadata.supabase_id로 남겨 검색된 질문에서 실제 답변(answer)을 다시 조회하는 구조로 쓴다.
-- coupang_faq_personal_info와 컬럼 구성을 동일하게 맞춰 retrieve.py에서 로직을 재사용한다.
CREATE TABLE coupang_faq_delivery (
    id SERIAL PRIMARY KEY,
    category TEXT,                             -- 질문 앞 대괄호에서 추출 (배송완료미수령, 상품파손 등)
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source TEXT NOT NULL,                       -- 데이터셋 출처 라벨(예: "공식 쿠팡 정책")
    source_url TEXT,                            -- 이 데이터셋은 전부 PDF 유래라 NULL
    source_pdf_file TEXT,                       -- 자주_묻는_질문_배송문의_ep_1.pdf 등
    source_pdf_question_number INT,             -- 그 PDF 안에서 몇 번째 질문인지
    source_pdf_note TEXT,                       -- 전부 PDF 유래라 항상 NULL(스키마 일관성을 위해 유지)
    UNIQUE (source_pdf_file, source_pdf_question_number)
);
