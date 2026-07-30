-- PostgreSQL 스키마 (12절 기술스택: PostgreSQL/MySQL)

-- 사용자용 문의 접수 페이지(/submit)에서 이름/연락처/문의 원문을 받아 저장하는 곳.
-- 접수(INSERT) 직후 서버가 바로 classify_node+rules_node만 실행해(RAG 검색·답변 생성은
-- 아직 안 함) inquiry_type/inquiry_types/department/candidate_departments/priority/
-- emotion을 채우고 status를 '검토중'으로 바꾼다 — "문의 유형 자동 확인"이 사용자
-- 페이지에 뜨는 시점이 바로 이때다. 이후 담당자가 내부 화면에서 실제 답변까지
-- 만들어 "최종 답변으로 저장"을 누르면 final_answer가 채워지고 status가
-- '답변완료'로 바뀐다. 담당부서가 틀렸을 때 직접 고치는 버튼은 내부 담당자
-- 화면(AI 분석 결과)에만 있고, 그 결과가 다시 이 테이블에 반영된다.
-- 아래 departments/inquiries 등은 AI 처리 결과까지 정규화해서 저장하려던 설계였으나
-- 실제로 생성된 적은 없다(2026-07-28 기준) — citizen_submissions는 그와 별개로,
-- 지금 당장 필요한 "원문 접수함 + 처리 상태 추적" 용도로 실제 사용 중인 테이블이다.
CREATE TABLE citizen_submissions (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    contact TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT '접수완료',  -- 접수완료 / 검토중 / 답변완료
    inquiry_type TEXT,               -- 주요문의유형 (분류 전엔 NULL)
    inquiry_types TEXT[],            -- 문의유형들(해당되는 유형 전체)
    department TEXT,                 -- 담당부서
    candidate_departments TEXT[],    -- 담당부서 후보 전체(rule_flags.candidate_departments)
    priority TEXT,                   -- 우선순위
    emotion TEXT,                    -- 감정상태
    core_request TEXT,               -- 핵심요청 (classify_node가 요약한 문의의 핵심 요청)
    classification_reason TEXT,      -- 분류근거 (classify_node의 LLM 분류 근거)
    requires_manager_review BOOLEAN NOT NULL DEFAULT false,  -- rule_flags.requires_manager_review (9절 민감 민원)
    matched_rules TEXT[],             -- rule_flags.matched_rules (규칙 엔진 매칭 경로)
    final_answer TEXT,               -- 담당자가 확정해 저장한 답변 (확정 전엔 NULL)
    sources TEXT[],                  -- final_answer의 근거 출처 라벨 목록 (확정 전엔 NULL/빈 배열)
    from_cache BOOLEAN NOT NULL DEFAULT false  -- query_cache 히트(유사도 0.90 이상)로 분류를 재사용했는지 여부
);

-- 담당자가 검토·확정한 최종 답변을 재사용하기 위한 전용 캐시 테이블.
-- citizen_submissions와 독립적이다 — 실제 문의에서 확정된 답변(submission_id가 채워짐)뿐
-- 아니라, seed_query_cache.py 같은 스크립트로 미리 심어둔 예시 문답(submission_id가 NULL)도
-- 같은 방식으로 담을 수 있다. raw_text 임베딩은 Chroma(answer_cache 컬렉션)에 두고,
-- 이 테이블의 id를 metadata.cache_id로 남겨 검색된 질문에서 실제 답변을 다시 조회한다.
CREATE TABLE answer_cache (
    id UUID PRIMARY KEY,
    raw_text TEXT NOT NULL,
    final_answer TEXT NOT NULL,
    sources TEXT[],
    submission_id UUID REFERENCES citizen_submissions(id),  -- 유래한 확정 문의 (seed 데이터는 NULL)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
