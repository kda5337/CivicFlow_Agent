from dotenv import load_dotenv

load_dotenv()  # Langfuse가 os.environ에서 자격증명을 읽기 전에 먼저 로드되어야 한다.

from app.core.tracing import get_langfuse_client, init_tracing  # noqa: E402

init_tracing()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.routers.departments import router as departments_router  # noqa: E402
from app.api.routers.inquiries import router as inquiries_router  # noqa: E402

app = FastAPI(title="CivicFlow Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inquiries_router)
app.include_router(departments_router)


@app.on_event("shutdown")
def shutdown_tracing() -> None:
    get_langfuse_client().shutdown()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}