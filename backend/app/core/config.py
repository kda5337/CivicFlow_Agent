from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 리포 루트/backend 절대경로. 상대경로("./chroma_db", ".env")를 쓰면 스크립트를
# 어느 작업 디렉터리에서 실행하느냐(backend/, 리포 루트, IDE 실행 버튼 등)에 따라
# 엉뚱한 위치를 가리키는 문제가 있었다 — 그래서 여기 파일 위치 기준 절대경로로 고정한다.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_REPO_ROOT / ".env"), extra="ignore")

    # 채팅 LLM: 업스테이지 Solar. 기본 모델 호출 실패 시 llm_model_fallback으로 자동 롤백한다.
    upstage_api_key: str = ""
    llm_model_primary: str = "solar-pro3"
    llm_model_fallback: str = "solar-pro2"

    # 임베딩은 한국어 특화 오픈소스 모델(KURE-v1)을 로컬에서 자체 호스팅한다. API 키 불필요.
    embedding_model: str = "nlpai-lab/KURE-v1"

    # 컬렉션 이름은 여기서 관리하지 않는다 — 각 ingest/조회 코드가 호출 시점에 직접 정한다.
    chroma_persist_dir: str = str(_BACKEND_DIR / "chroma_db")
    rag_top_k: int = 1

    # 졸업요건/교육과정 문의를 SQL로 직접 조회하는 데 쓰는 Supabase(Postgres) 연결.
    supabase_database_url: str = ""

    # data.go.kr(공공데이터포털) 파일데이터 Open API 인증키. 15118694(제주관광공사
    # 온라인면세점 자주묻는 질문) 등 odcloud.kr 기반 API 호출에 쓴다.
    data_go_kr_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
