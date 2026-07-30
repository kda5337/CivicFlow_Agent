# CivicFlow_Agent

AI + RAG 기반 민원·문의 자동 분류 및 답변 초안 생성 시스템 (가천대 AI 부트캠프 과제)

## 아키텍처

LangGraph `StateGraph`로 4절 시스템 흐름을 노드 단위로 구현했다.

```
START -> intake --+-> reject -> END                      (관련없는 입력)
                   +-> classify -> apply_rules --+-> retrieve -> generate -> END
                                                  +-> manager_review -> END   (민감 민원 감지 시)
```

| 노드 | 파일 | 역할 |
|---|---|---|
| intake | `backend/app/graph/nodes/intake.py` | 문의접수, 입력 검증, 학사행정 민원·문의 관련성 판별 |
| reject | `backend/app/graph/nodes/intake_reply.py` | (관련없음) 발랄한 페르소나로 재질문 요청 답변 생성 후 종료 |
| classify | `backend/app/graph/nodes/classify.py` | LLM 유형/우선순위/담당부서 분류 (7절, 업스테이지 Solar) |
| apply_rules | `backend/app/graph/nodes/rules.py` | 키워드 Rule로 분류 보정 (9절, `backend/rules.yaml`) |
| retrieve | `backend/app/graph/nodes/retrieve.py` | RAG 근거 문서 검색 (8절) |
| generate | `backend/app/graph/nodes/generate.py` | 답변 초안 생성 |
| manager_review | `backend/app/graph/nodes/manager_review.py` | 민감 민원 즉시 관리자 검토 라우팅 |

그래프 조립: `backend/app/graph/build.py`

## LLM

채팅 LLM은 업스테이지 Solar를 사용한다 (`backend/app/core/llm.py`).
`solar-pro-3`를 기본으로 호출하고, 실패 시 LangChain `with_fallbacks`로 `solar-pro-2`에 자동 롤백된다.
모델명은 `.env`의 `LLM_MODEL_PRIMARY` / `LLM_MODEL_FALLBACK`으로 바꿀 수 있다.
임베딩(RAG 벡터화)은 한국어 특화 오픈소스 모델(`nlpai-lab/KURE-v1`)을 `sentence-transformers`로 로컬에서 자체 호스팅한다 (API 키 불필요, `.env`의 `EMBEDDING_MODEL`로 변경 가능).

## 트레이싱 (Langfuse)

`backend/app/core/tracing.py`에서 초기화한다. 요청 하나(`POST /inquiries`)가 트레이스 하나로 묶인다.

- 루트 span(`process-inquiry`)의 input은 문의 원문만 노출 — 내부 state 전체를 흘리지 않는다.
- `propagate_attributes`로 `session_id`(=inquiry_id), `tags`를 하위 모든 span에 전파.
- `CallbackHandler`를 LangGraph에 붙여 `classify`/`generate`의 LLM 호출(모델명·토큰 사용량 포함)이 자동 캡처된다.
- `retrieve`(Chroma 검색)는 `retriever`, `apply_rules`는 `tool`, `manager_review` 분기는 `level=WARNING` span으로 명시적 타입 지정.
- `mask_otel_spans`로 이메일/휴대폰번호를 export 시점에 마스킹.
- 요청 응답에 `trace_url`을 포함해 담당자가 바로 해당 트레이스로 이동할 수 있게 함 (Langfuse 설정이 없거나 실패해도 본 응답은 절대 실패하지 않도록 방어 처리됨).
- `LANGFUSE_TRACING_ENVIRONMENT=development`로 개발 중 트레이스와 운영 트레이스를 분리 (Langfuse UI에서 environment로 필터링 가능).
- `session_id`는 쓰지 않는다: 이 API는 대화형이 아닌 단건 요청-응답이라 세션으로 묶을 다른 트레이스가 없다. 대신 `inquiry_id`는 DB 대조용으로 metadata에만 넣는다.

Langfuse UI에서 확인할 것: Traces 뷰에서 노드별 span 계층, `classify`/`generate` 아래의 generation(모델·토큰·비용), `apply_rules`의 before/after 분류값, 민감 민원이면 뜨는 `escalate-to-manager-review` 경고 span.

## 폴더 구조

```
backend/          FastAPI + LangGraph 백엔드 코드
  app/core/        설정, LLM 래퍼, Langfuse 트레이싱 초기화
  app/graph/       StateGraph 및 노드
  app/rag/         Vector DB(Chroma) 적재/검색
  app/api/         FastAPI 라우터
  rules.yaml       Rule 엔진 설정
data/
  ai_hub/          AI Hub 원본 데이터 (5-1절)
  self_collected/  팀 자체수집 샘플 (5-2절)
  knowledge_base/  RAG 원본 문서 (FAQ/매뉴얼/규정)
eval/metrics.py    13절 평가지표 목표값
db/schema.sql      PostgreSQL 스키마
frontend/          화면 6개 (11절) 예정 위치
docs/              14절 최종 산출물
requirements.txt   의존성 (리포 루트)
.env / .env.example  환경변수 (리포 루트)
```

## 실행 방법

`requirements.txt`와 `.env`는 리포 루트에 있다 (venv는 어디서 만들든 상관없고, 앱 실행은 `backend/`에서 한다).

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows, 리포 루트에서
pip install -r requirements.txt
copy .env.example .env   # UPSTAGE_API_KEY, LANGFUSE_PUBLIC/SECRET_KEY 입력

cd backend
python -m app.rag.ingest      # RAG 지식베이스 적재
uvicorn app.main:app --reload
```

테스트:
```bash
curl -X POST http://localhost:8000/inquiries -H "Content-Type: application/json" -d "{\"text\": \"수강신청을 했는데 신청 내역이 보이지 않습니다. 오늘 안에 처리해야 합니다.\"}"
```
응답의 `trace_url`을 열면 방금 처리된 문의의 Langfuse 트레이스를 바로 볼 수 있다.
