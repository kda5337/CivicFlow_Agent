# CivicFlow_Agent
http://34.47.93.32:8080/

AI + RAG 기반 민원·문의 자동 분류 및 답변 초안 생성 시스템 (AI 부트캠프 과제)

파이프라인 자체(분류→Rule 보정→RAG 검색→답변 초안 생성)는 도메인에 종속되지 않지만,
현재 RAG 지식베이스와 예시 데이터는 이커머스·공공서비스 FAQ(쿠팡 고객센터, 제주관광공사
온라인면세점, 사내 부서별 FAQ, AI Hub 상담데이터)로 구성되어 있다.

## 문의 처리 흐름 (2개 접수 경로)

1. **시민용 접수 페이지** (`POST /submissions`) — 이름/연락처/문의 원문을 받아 관련성
   판별 + LLM 유형분류 + Rule 보정까지만 즉시 실행하고 `citizen_submissions`에 저장한다
   (RAG 검색·답변 생성은 아직 하지 않음). 사용자는 이 결과("문의 유형 자동 확인")를
   접수 즉시 확인할 수 있다.
2. **담당자 내부 화면 "문의 접수함"** — 담당자가 접수된 건을 확인하고 "AI 처리 →"를
   누르면, 비슷한 과거 문의에 이미 담당자가 승인한 답변(`answer_cache`)이 있는지 먼저
   확인해 팝업으로 물어본다. 승인된 캐시를 안 쓰기로 하면 `POST /inquiries`가 (이미
   끝난 관련성 판별/분류는 재실행하지 않고) RAG 검색 + 답변 초안 생성만 수행한다.
   이후 화면(AI 분석 결과 → RAG 검색 결과 → 답변 초안 편집 → 검토 완료)을 거쳐
   "검토 완료 & 등록"을 누르면 `final_answer`가 확정되고, 그 결과가 `answer_cache`에도
   등록되어 이후 비슷한 문의에 재사용된다.

관리자용 "테스트" 섹션은 `citizen_submissions`를 거치지 않고 `POST /inquiries`
(submission_id 없이)를 직접 호출해 전체 그래프(관련성 판별부터)를 그대로 실행해본다.

## 아키텍처

LangGraph `StateGraph`로 구현했다 (`backend/app/graph/build.py`).

```
START -> check_cache --+-> END                                       (의미 캐시 HIT)
                        +-> intake --+-> reject -> END                (관련없는 입력)
                                     +-> classify -> apply_rules -> retrieve -> generate -> store_cache -> END
```

| 노드 | 파일 | 역할 |
|---|---|---|
| check_cache | `backend/app/graph/nodes/cache.py` | 의미 캐시(`query_cache`) 조회. 유사한 과거 문의가 있으면 나머지 노드를 전부 건너뛴다 |
| intake | `backend/app/graph/nodes/intake.py` | 입력 검증, 처리 대상 민원·문의 관련성 LLM 판별 |
| reject | `backend/app/graph/nodes/intake_reply.py` | (관련없음) 발랄한 페르소나로 재질문 요청 답변 생성 후 종료 |
| classify | `backend/app/graph/nodes/classify.py` | LLM 유형/핵심요청/감정상태 분류 (업스테이지 Solar) |
| apply_rules | `backend/app/graph/nodes/rules.py` | 키워드 Rule로 담당부서/우선순위 결정 (`backend/rules.yaml`), 민감 민원이면 `rule_flags.requires_manager_review` 플래그만 세팅 |
| retrieve | `backend/app/graph/nodes/retrieve.py` | RAG 근거 문서(FAQ) 검색 |
| generate | `backend/app/graph/nodes/generate.py` | 답변 초안 생성 |
| store_cache | `backend/app/graph/nodes/cache.py` | 끝까지 실행된(캐시 MISS였던) 결과를 `query_cache`에 저장 |

`관리자검토필요`는 더 이상 그래프 분기가 아니다 — 예전에는 `manager_review` 노드가
generate를 건너뛰고 정적 안내문으로 대체했지만, 지금은 민감 민원이어도 RAG 검색+답변
초안 생성을 다른 문의와 똑같이 수행한다. 신호 자체는 `rule_flags.requires_manager_review`
로 계속 전달되어 화면에서 우선 검토 대상으로 표시하는 데만 쓰인다.
(`backend/app/graph/nodes/manager_review.py`는 더 이상 그래프에 등록되지 않는 죽은 코드다.)

테스트 섹션에서 온 요청(`is_test=True`)은 `check_cache`/`store_cache`를 항상 건너뛴다 —
테스트 데이터가 실제 의미 캐시를 오염시키지 않게 하기 위함이다.

## LLM

채팅 LLM은 업스테이지 Solar를 사용한다 (`backend/app/core/llm.py`).
`solar-pro3`를 기본으로 호출하고, 실패 시 LangChain `with_fallbacks`로 `solar-pro2`에 자동 롤백된다.
모델명은 `.env`의 `LLM_MODEL_PRIMARY` / `LLM_MODEL_FALLBACK`으로 바꿀 수 있다.
임베딩(RAG 벡터화)은 한국어 특화 오픈소스 모델(`nlpai-lab/KURE-v1`)을 `sentence-transformers`로 로컬에서 자체 호스팅한다 (API 키 불필요, `.env`의 `EMBEDDING_MODEL`로 변경 가능).

## RAG & 데이터 소스

실제 검색 대상은 `chroma_merged_faq` 컬렉션(여러 FAQ 출처의 질문 임베딩) 하나다
(`backend/app/graph/nodes/retrieve.py`). 검색된 문서의 `metadata.source_table`/
`supabase_id`로 Supabase를 역조회해 실제 답변(answer)을 가져온다 — 질문만 벡터로,
답변 본문은 Postgres에 그대로 둔다.

`data/knowledge_base`(FAQ/매뉴얼 마크다운)를 위한 `knowledge_base` 컬렉션도 존재하지만,
현재 실제 문서가 적재되어 있지 않아(0건) 검색에 쓰이지 않는다. `backend/app/rag/ingest.py`
(`python -m app.rag.ingest`)를 그대로 돌려도 이 미사용 컬렉션만 채워질 뿐, 실제 답변
검색 결과에는 영향이 없다.

`chroma_merged_faq`를 실제로 채우는 것은 `backend/app/rag/merge_chroma_faq.py`이며, 그 전에
각 출처를 Supabase + 개별 Chroma 컬렉션으로 적재하는 `ingest_*.py` 스크립트들이 있다:

| 스크립트 | 출처 |
|---|---|
| `ingest_coupang_faq.py` / `ingest_coupang_delivery_faq.py` / `ingest_coupang_order_payment_faq.py` / `ingest_coupang_personal_info_faq.py` | 쿠팡 고객센터 FAQ (PDF 6종 + 뉴스룸 정책) |
| `ingest_duty_free_faq.py` | data.go.kr(공공데이터포털) 15118694 — 제주관광공사 온라인면세점 FAQ |
| `ingest_it_support_faq.py` / `ingest_marketing_promotion_faq.py` / `ingest_admin_team_faq.py` / `ingest_legal_team_faq.py` / `ingest_sensitive_complaint_faq.py` / `ingest_safety_team_faq.py` | 사내 부서별(IT지원팀/마케팅팀/행정팀/법무팀/고객지원총괄팀/안전관리팀) FAQ |
| `build_coupang_faq.py` | 쿠팡 FAQ 원본 통합용 전처리 |
| `ocr_toc.py` / `pdf_toc.py` | PDF 목차 OCR/추출 보조 스크립트 |

`app/rag/knowledge_base.py`가 이 FAQ 테이블 화이트리스트(`FAQ_TABLES`)와 지식베이스
관리 화면(CRUD/재처리)용 로직을 담는다. `data_go_kr_api_key`(`.env`)는 면세점 FAQ 수집에,
`supabase_database_url`은 이 모든 FAQ 테이블 및 `citizen_submissions`/`answer_cache`의
실제 저장소로 쓰인다.

`db/schema.sql`에는 이 외에도 `departments`/`inquiries`/`retrieved_evidence`/`answer_drafts`
(정규화 저장을 시도했으나 실제로 생성된 적 없는 초기 설계)와 `graduation_requirements`/
`curriculum_courses`(학사 도메인용 SQL 조회를 위해 만든 테이블이나 현재 이를 조회하는
노드/라우터 코드는 없음)가 남아있다 — 지금 실제로 쓰이는 테이블은 `citizen_submissions`,
`answer_cache`, 그리고 위 FAQ 테이블들뿐이다.

## 캐싱 (2단계, 서로 독립)

| | `query_cache` (`backend/app/rag/query_cache.py`) | `answer_cache` (`backend/app/rag/answer_cache.py`) |
|---|---|---|
| 저장 시점 | 그래프가 끝까지 실행된(사람 검토 전) 분류+RAG+초안 결과 | 담당자가 "검토 완료 & 등록"으로 확정한 답변 |
| 재사용 시점 | 새 문의 접수 시(그래프 `check_cache`, 시민 접수 `POST /submissions`) | 담당자가 "AI 처리" 실행 시(`answer-cache-check`) |
| 기본 유사도 임계값 | 0.80 (시민 접수 경로는 0.90으로 더 엄격) | 0.90 |
| 저장소 | Chroma(`query_cache` 컬렉션), 메타데이터에 결과 전체를 JSON으로 보관 | Chroma(`answer_cache` 컬렉션, 임베딩만) + Supabase `answer_cache` 테이블(실제 답변) |

두 캐시 모두 `rule_flags.requires_manager_review=true`였던 결과는 저장하지 않는다 —
민감 민원은 텍스트가 비슷해도 매번 사람이 다시 판단해야 하기 때문이다.

## 트레이싱 (Langfuse)

`backend/app/core/tracing.py`에서 초기화한다. 요청 하나(`POST /inquiries`)가 트레이스 하나로 묶인다.

- 루트 span(`process-inquiry`)의 input은 문의 원문만 노출 — 내부 state 전체를 흘리지 않는다.
- `propagate_attributes`로 `inquiry_id`(metadata), `tags`를 하위 모든 span에 전파.
- `CallbackHandler`를 LangGraph에 붙여 `classify`/`generate`의 LLM 호출(모델명·토큰 사용량 포함)이 자동 캡처된다.
- `check_cache`/`retrieve`(Chroma 검색)는 `retriever`, `apply_rules`는 `tool` 타입 span으로 명시적 타입 지정.
- `mask_otel_spans`로 이메일/휴대폰번호를 export 시점에 마스킹.
- 요청 응답에 `trace_url`을 포함해 담당자가 바로 해당 트레이스로 이동할 수 있게 함 (Langfuse 설정이 없거나 실패해도 본 응답은 절대 실패하지 않도록 방어 처리됨).
- `LANGFUSE_TRACING_ENVIRONMENT=development`로 개발 중 트레이스와 운영 트레이스를 분리 (Langfuse UI에서 environment로 필터링 가능).
- `session_id`는 쓰지 않는다: 이 API는 대화형이 아닌 단건 요청-응답이라 세션으로 묶을 다른 트레이스가 없다. 대신 `inquiry_id`는 DB 대조용으로 metadata에만 넣는다.

Langfuse UI에서 확인할 것: Traces 뷰에서 노드별 span 계층, `classify`/`generate` 아래의 generation(모델·토큰·비용), `apply_rules`의 before/after 분류값, `check_cache`의 캐시 HIT/MISS.

## API

FastAPI 라우터는 `backend/app/api/routers/`에 있다 (`backend/app/main.py`에서 등록).

| 라우터 | 주요 엔드포인트 | 역할 |
|---|---|---|
| `inquiries` | `POST /inquiries`, `POST /inquiries/answer-cache-check`, `POST /inquiries/regenerate-answer` | 그래프 실행/캐시 확인/문서 재선택 재생성 |
| `submissions` | `POST /submissions`, `GET /submissions`, `POST /submissions/check-relevance`, `POST /submissions/cache-check`, `PATCH /submissions/{id}/classification`, `PATCH /submissions/{id}/answer` | 시민 접수, 목록 조회, 관련성/캐시 사전 확인, 분류·답변 확정 반영 |
| `departments` | `GET /departments` | `rules.yaml` 기준 담당부서 전체 목록 |
| `knowledge_base` | `GET/POST/PATCH/DELETE /knowledge-base/{table}/items`, `POST /knowledge-base/{table}/reprocess`, `GET/DELETE /knowledge-base/answer-cache*` | FAQ 원본 CRUD·재임베딩, 답변 캐시 목록/삭제 |

`GET /health`는 시크릿 없이도 200을 반환한다(배포 헬스체크용). 로컬 개발 시 CORS는
`http://localhost:5173`, `5174`, `3000`(프런트 dev 서버)에 허용되어 있다.

## 프런트엔드

`frontend/`는 React 18 + Vite 기반 SPA다.

```
frontend/src/
  views/       9개 화면 (viewsConfig.js): 대시보드/문의 접수함/답변 완료함/
               AI 분석 결과/RAG 검색 결과/답변 초안 편집/검토 완료/지식베이스 관리/테스트
  components/  Sidebar/Topbar/Pipeline 등 공용 컴포넌트
  useInquiryPipeline.js  문의 처리 파이프라인 상태·API 호출을 모아둔 훅 (App.jsx/StaffView.jsx가 공유)
  config.js    API base URL (dev: localhost:8000 절대경로, 배포: "" 상대경로+nginx 프록시)
```

`useInquiryPipeline`은 `POST /inquiries` 단발성 호출로 결과를 받아온다(폴링 방식이 아니다).

실행:
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, 백엔드(8000)와 함께 띄워야 함
```

## CI/CD & 배포

- `.github/workflows/ci.yml`: main에 push/PR 시 ruff lint, mypy(비차단), pytest(`backend/tests`,
  시크릿 없이 도는 스모크 테스트만), 프런트 eslint+build, gitleaks 시크릿 스캔을 실행한다.
- `.github/workflows/cd.yml`: CI 성공 시(또는 수동 dispatch) api/frontend 이미지를 빌드해
  GHCR에 push하고, SSH로 GCE VM(lumi-agent)에 배포한다. `.env`는 매 배포마다 GitHub
  Secrets로 재생성되고, 배포 후 `/health`를 재시도하며 헬스체크에 실패하면 이전 이미지로
  자동 롤백한다. `workflow_dispatch(rollback: true)`로 수동 롤백도 가능하다.
- `Dockerfile.api`: CPU 전용 torch + `requirements-api.txt`(배포 전용 의존성 부분집합)를 설치하고
  빌드 시점에 KURE-v1 임베딩 모델을 미리 캐시한다. 8000 포트로 기동.
- `Dockerfile.frontend`: Vite 빌드(`VITE_API_BASE_URL=""`) 후 nginx로 정적 서빙(80 포트,
  `frontend/nginx.conf`가 API 경로를 백엔드 컨테이너로 프록시).
- `docker-compose.yml`(로컬): 두 Dockerfile을 직접 빌드, api `8000`/frontend `8080`,
  `./backend/chroma_db` 볼륨 마운트.
- `docker-compose.prod.yml`(배포): GHCR의 사전 빌드 이미지를 pull, VM에 이미 다른 프로젝트가
  호스트 8000을 쓰고 있어 api는 `8001:8000`으로 매핑, `./chroma_db`(리포 루트 기준) 볼륨 마운트.

## 평가 & 테스트

- `backend/tests`: CI(`ci.yml`)가 실행하는 시크릿 불필요 스모크/순수함수 테스트.
- `test/run_classification_eval.py`, `test/run_full_eval.py`: 실제 LLM/DB 호출이 필요한
  분류·전체 파이프라인 평가 스크립트(`test/test_cases.py`에 케이스, `test/eval_config.py`에 설정) —
  비용·속도·비결정성 때문에 CI에는 넣지 않고 필요할 때 수동으로 돌린다.
- `test/visualize_eval_results.py`: 평가 결과 시각화, 결과는 `test/results/`에 저장.
- `eval/metrics.py`: 13절 평가지표 목표값 정의.
- `docs/`: 일자별 작업 로그, 화면설계/Rule Engine/RAG 설계 문서, 14절 최종 산출물 체크리스트(`docs/README.md`).

## 폴더 구조

```
backend/          FastAPI + LangGraph 백엔드 코드
  app/core/        설정, LLM 래퍼, Langfuse 트레이싱 초기화
  app/graph/       StateGraph 및 노드
  app/rag/         Vector DB(Chroma) 적재/검색, query_cache/answer_cache, 지식베이스 CRUD
  app/api/         FastAPI 라우터
  rules.yaml       Rule 엔진 설정
  requirements-dev.txt  CI(lint/typecheck/test)용 의존성
data/
  ai_hub/          AI Hub 원본 데이터
  self_collected/  팀 자체수집 샘플
  knowledge_base/  RAG 원본 문서(FAQ/매뉴얼) — 현재 검색에는 미사용(0건 적재)
db/schema.sql      PostgreSQL(Supabase) 스키마 — 일부 테이블은 미사용/설계 단계 (본문 "RAG & 데이터 소스" 참고)
eval/metrics.py    13절 평가지표 목표값
frontend/          React + Vite SPA (9개 화면)
docs/              작업 로그 및 14절 최종 산출물
test/              LLM/DB를 실제로 호출하는 평가 스크립트 (CI 미포함)
requirements.txt   로컬 개발용 전체 의존성 (리포 루트)
requirements-api.txt  Dockerfile.api 배포용 의존성 부분집합 (리포 루트)
Dockerfile.api / Dockerfile.frontend / docker-compose*.yml  컨테이너 빌드/배포
.env / .env.example  환경변수 (리포 루트)
```

## 실행 방법

`requirements.txt`와 `.env`는 리포 루트에 있다 (venv는 어디서 만들든 상관없고, 앱 실행은 `backend/`에서 한다).

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows, 리포 루트에서
pip install -r requirements.txt
copy .env.example .env   # UPSTAGE_API_KEY, SUPABASE_DATABASE_URL, LANGFUSE_PUBLIC/SECRET_KEY 등 입력

cd backend
uvicorn app.main:app --reload
```

RAG 검색이 실제로 참조하는 `chroma_merged_faq`를 채우려면 `data_go_kr_api_key`/
`supabase_database_url`을 설정한 뒤 `app/rag/ingest_*.py` 각 스크립트 → `app/rag/merge_chroma_faq.py`
순으로 실행해야 한다 (`python -m app.rag.ingest`만 돌리면 검색에 쓰이지 않는
`knowledge_base` 컬렉션만 채워진다).

테스트:
```bash
curl -X POST http://localhost:8000/inquiries -H "Content-Type: application/json" -d "{\"text\": \"주문한 상품이 아직 도착하지 않았는데 확인 부탁드립니다.\", \"is_test\": true}"
```
응답의 `trace_url`을 열면 방금 처리된 문의의 Langfuse 트레이스를 바로 볼 수 있다.
