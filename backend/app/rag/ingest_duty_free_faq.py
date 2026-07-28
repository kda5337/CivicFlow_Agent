"""data.go.kr 15118694('제주관광공사_온라인면세점 자주묻는 질문')를
Supabase(답변 저장) + Chroma(질문만 임베딩) 구조로 RAG에 적재한다.

이전에 같은 구조로 실험해 두었던 chroma_cancel_category(AI Hub 취소/환불 상담 데이터)
컬렉션은 이 데이터로 대체한다 — reset_chroma_collection()이 그 컬렉션만 지우고,
실제 서비스 RAG 검색(retrieve_node)이 쓰는 knowledge_base 컬렉션은 건드리지 않는다.

data.go.kr Open API(odcloud.kr) 응답 컬럼:
    자주묻는질문아이디, 자주묻는질문타입, 자주묻는질문제목, 자주묻는질문내용,
    자주묻는질문상태, 자주묻는질문랭킹설정여부, 자주묻는질문랭킹, 등록일시, 수정일시
질문(자주묻는질문제목)만 그대로 Chroma에 임베딩하고, 답변(자주묻는질문내용)은
Supabase에만 저장한 뒤 metadata.supabase_id로 역참조한다. LLM 가공 없음.

실행:
    cd backend
    python -m app.rag.ingest_duty_free_faq fetch                # Open API에서 받아 파일로 저장
    python -m app.rag.ingest_duty_free_faq fetch --dry-run      # 5건만 시험
    python -m app.rag.ingest_duty_free_faq load-supabase        # Supabase(duty_free_faq)에만 적재
    python -m app.rag.ingest_duty_free_faq reset-chroma         # 기존 chroma_cancel_category 컬렉션 삭제
    python -m app.rag.ingest_duty_free_faq load-chroma          # 질문만 새 컬렉션에 임베딩 (Supabase에 먼저 있어야 함)
    python -m app.rag.ingest_duty_free_faq test                 # '환불은 어떻게 하는거야'로 검색 테스트
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# IDE의 "실행" 버튼처럼 이 파일을 모듈(-m)이 아니라 직접 파일 경로로 실행하는 경우,
# backend/가 sys.path에 없어서 `app.*` 임포트가 실패한다. 그런 경우를 대비해 보정한다.
_BACKEND_DIR = str(Path(__file__).resolve().parents[2])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import psycopg2
from langchain_core.documents import Document
from tqdm import tqdm

from app.core.config import get_settings
from app.rag.vectorstore import get_vectorstore

# 15118694 데이터셋의 최신 버전(2025.05.28) uddi. data.go.kr fileData 페이지의
# OpenAPI(Swagger) 탭에서 확인한 값.
DATASET_ENDPOINT = (
    "https://api.odcloud.kr/api/15118694/v1/uddi:4b8fa3a1-ddab-4d43-a425-9f59dbf8b178"
)

OUTPUT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "data_go_kr" / "jeju_duty_free_faq.json"
)

OLD_CHROMA_COLLECTION_NAME = "chroma_cancel_category"  # AI Hub 실험용 - 이 스크립트가 대체
CHROMA_COLLECTION_NAME = "chroma_duty_free_faq"

# 이 데이터가 어느 데이터셋에서 왔는지 Supabase에 함께 남기기 위한 출처 식별자.
DATASET_SOURCE = "data.go.kr:제주면세점_FAQ"

# 답변 각주에 "어느 공공데이터의 어떤 정보인지"를 보여주기 위한 상세 출처 정보.
DATASET_ID = "15118694"
DATASET_NAME = "제주관광공사_온라인면세점 자주묻는 질문"


def fetch_page(api_key: str, page: int, per_page: int = 100) -> dict:
    query = urllib.parse.urlencode(
        {"page": page, "perPage": per_page, "returnType": "JSON", "serviceKey": api_key}
    )
    request = urllib.request.Request(f"{DATASET_ENDPOINT}?{query}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SystemExit(f"data.go.kr 요청 실패 ({error.code}): {error.read().decode('utf-8')}")


def fetch_all(api_key: str) -> list[dict]:
    records: list[dict] = []
    page = 1
    while True:
        body = fetch_page(api_key, page)
        page_data = body.get("data", [])
        if not page_data:
            break
        records.extend(page_data)
        if len(records) >= body.get("totalCount", 0):
            break
        page += 1
    return records


def fetch(dry_run: bool = False) -> list[dict]:
    """Open API에서 전체 FAQ를 내려받아 파일로 저장한다. DB에는 쓰지 않는다."""
    settings = get_settings()
    if not settings.data_go_kr_api_key:
        raise SystemExit("DATA_GO_KR_API_KEY가 .env에 설정되어 있지 않습니다.")

    records = fetch_all(settings.data_go_kr_api_key)
    print(f"{len(records)}건을 내려받았습니다.")

    if dry_run:
        records = records[:5]
        print(f"--dry-run: {len(records)}건만 저장합니다.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(records)}건을 {OUTPUT_PATH}에 저장했습니다.")
    return records


def load_records() -> list[dict]:
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


def ensure_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS duty_free_faq (
            id SERIAL PRIMARY KEY,
            faq_id INT NOT NULL UNIQUE,
            faq_type TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            registered_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ,
            source TEXT NOT NULL DEFAULT 'data.go.kr:15118694',
            source_dataset_id TEXT,
            source_dataset_name TEXT,
            source_faq_type_index INT
        )
        """
    )
    # 이미 배포된 테이블에는 CREATE TABLE IF NOT EXISTS가 컬럼을 추가해주지 않으므로 별도 보정.
    cur.execute(
        "ALTER TABLE duty_free_faq ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'data.go.kr:15118694'"
    )
    cur.execute("ALTER TABLE duty_free_faq ADD COLUMN IF NOT EXISTS source_dataset_id TEXT")
    cur.execute("ALTER TABLE duty_free_faq ADD COLUMN IF NOT EXISTS source_dataset_name TEXT")
    cur.execute("ALTER TABLE duty_free_faq ADD COLUMN IF NOT EXISTS source_faq_type_index INT")


def assign_faq_type_index(records: list[dict]) -> None:
    """faq_type(자주묻는질문타입)별로 원본 순서 그대로 1부터 매기는 순번을
    각 record에 "source_faq_type_index"로 채워 넣는다."""
    counters: dict[str, int] = {}
    for record in records:
        faq_type = record.get("자주묻는질문타입")
        counters[faq_type] = counters.get(faq_type, 0) + 1
        record["source_faq_type_index"] = counters[faq_type]


def upsert_faq(cur, record: dict) -> int:
    cur.execute(
        """
        INSERT INTO duty_free_faq
            (faq_id, faq_type, question, answer, registered_at, updated_at, source,
             source_dataset_id, source_dataset_name, source_faq_type_index)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (faq_id)
        DO UPDATE SET
            faq_type = EXCLUDED.faq_type,
            question = EXCLUDED.question,
            answer = EXCLUDED.answer,
            registered_at = EXCLUDED.registered_at,
            updated_at = EXCLUDED.updated_at,
            source = EXCLUDED.source,
            source_dataset_id = EXCLUDED.source_dataset_id,
            source_dataset_name = EXCLUDED.source_dataset_name,
            source_faq_type_index = EXCLUDED.source_faq_type_index
        RETURNING id
        """,
        (
            record["자주묻는질문아이디"],
            record.get("자주묻는질문타입"),
            record["자주묻는질문제목"],
            record["자주묻는질문내용"],
            record.get("등록일시") or None,
            record.get("수정일시") or None,
            DATASET_SOURCE,
            DATASET_ID,
            DATASET_NAME,
            record.get("source_faq_type_index"),
        ),
    )
    return cur.fetchone()[0]


def ingest_supabase(dry_run: bool = False) -> int:
    """fetch()가 저장한 파일을 읽어 Supabase(duty_free_faq)에만 저장한다. Chroma는 건드리지 않는다."""
    records = load_records()
    print(f"{len(records)}건의 FAQ를 불러왔습니다.")

    # dry-run으로 일부만 잘라내더라도 순번은 항상 전체 30건 기준으로 매겨야
    # faq_type별 순번이 원본과 어긋나지 않으므로, 자르기 전에 먼저 계산한다.
    assign_faq_type_index(records)

    if dry_run:
        records = records[:5]
        print(f"--dry-run: {len(records)}건만 적재합니다.")

    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn, conn.cursor() as cur:
            ensure_table(cur)
            for record in records:
                upsert_faq(cur, record)
    finally:
        conn.close()

    print(f"{len(records)}건을 Supabase(duty_free_faq)에 적재했습니다.")
    return len(records)


def reset_chroma_collection(collection_name: str = OLD_CHROMA_COLLECTION_NAME) -> None:
    """기존 실험용 컬렉션을 삭제한다. knowledge_base 등 다른 컬렉션은 건드리지 않는다."""
    vectorstore = get_vectorstore(collection_name)
    vectorstore.delete_collection()
    print(f"'{collection_name}' 컬렉션을 삭제했습니다.")


def fetch_faq_id(cur, faq_id: int) -> int | None:
    cur.execute("SELECT id FROM duty_free_faq WHERE faq_id = %s", (faq_id,))
    row = cur.fetchone()
    return row[0] if row else None


def ingest_chroma(dry_run: bool = False) -> int:
    """Supabase에 이미 적재된 faq_id로 id를 다시 조회해, 질문(자주묻는질문제목)만
    임베딩해 Chroma(chroma_duty_free_faq)에 저장한다."""
    records = load_records()
    print(f"{len(records)}건의 FAQ를 불러왔습니다.")

    if dry_run:
        records = records[:5]
        print(f"--dry-run: {len(records)}건만 적재합니다.")

    settings = get_settings()
    vectorstore = get_vectorstore(CHROMA_COLLECTION_NAME)

    documents = []
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn, conn.cursor() as cur:
            for record in tqdm(records, desc="Supabase 조회"):
                faq_id = record["자주묻는질문아이디"]
                supabase_id = fetch_faq_id(cur, faq_id)
                if supabase_id is None:
                    tqdm.write(f"경고: Supabase에 없는 FAQ라 건너뜀 - faq_id={faq_id}")
                    continue
                documents.append(
                    Document(
                        page_content=record["자주묻는질문제목"],
                        metadata={
                            "supabase_id": supabase_id,
                            "faq_id": faq_id,
                            "faq_type": record.get("자주묻는질문타입") or "",
                        },
                    )
                )
    finally:
        conn.close()

    batch_size = 50
    batches = [documents[start : start + batch_size] for start in range(0, len(documents), batch_size)]
    for batch in tqdm(batches, desc="Chroma 임베딩", unit="batch"):
        vectorstore.add_documents(batch)

    print(f"{len(documents)}건을 Chroma('{CHROMA_COLLECTION_NAME}')에 적재했습니다.")
    return len(documents)


def search_answer(query: str, k: int = 1) -> list[dict]:
    """Chroma(chroma_duty_free_faq)에서 query와 가장 유사한 질문을 찾고,
    metadata.supabase_id로 Supabase(duty_free_faq)에서 실제 답변을 조회한다."""
    vectorstore = get_vectorstore(CHROMA_COLLECTION_NAME)
    results = vectorstore.similarity_search_with_relevance_scores(query, k=k)

    settings = get_settings()
    matches = []
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        with conn.cursor() as cur:
            for doc, score in results:
                supabase_id = doc.metadata.get("supabase_id")
                cur.execute("SELECT answer FROM duty_free_faq WHERE id = %s", (supabase_id,))
                row = cur.fetchone()
                matches.append(
                    {
                        "score": score,
                        "question": doc.page_content,
                        "supabase_id": supabase_id,
                        "answer": row[0] if row else None,
                    }
                )
    finally:
        conn.close()

    return matches


def test_search_refund() -> None:
    """테스트: '환불은 어떻게 하는거야' 질문으로 검색해 결과를 출력한다."""
    query = "환불은 어떻게 하는거야"
    matches = search_answer(query, k=1)

    if not matches:
        print("검색 결과가 없습니다.")
        return

    best = matches[0]
    print(f"질문: {query}")
    print(f"유사도(score): {best['score']}")
    print(f"가장 유사한 page_content: {best['question']}")
    print()
    print(f"Supabase 답변(id={best['supabase_id']}):")
    print(best["answer"])


if __name__ == "__main__":
    args = sys.argv[1:]
    command = args[0] if args and not args[0].startswith("--") else "fetch"
    dry_run = "--dry-run" in args

    if command == "fetch":
        fetch(dry_run=dry_run)
    elif command == "load-supabase":
        ingest_supabase(dry_run=dry_run)
    elif command == "reset-chroma":
        reset_chroma_collection()
    elif command == "load-chroma":
        ingest_chroma(dry_run=dry_run)
    elif command == "test":
        test_search_refund()
    else:
        raise SystemExit(f"알 수 없는 명령: {command}")
