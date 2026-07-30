"""앱이 시크릿 없이도(빈 환경변수) import/기동에 실패하지 않는지 확인하는 스모크 테스트.
실제 DB/LLM 호출은 하지 않는다 — /health는 하드코딩된 값만 반환한다."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
