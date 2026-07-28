from functools import lru_cache
from typing import TypeVar

from langchain_upstage import ChatUpstage
from pydantic import BaseModel

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


def _build_chat(model: str, temperature: float) -> ChatUpstage:
    settings = get_settings()
    return ChatUpstage(model=model, api_key=settings.upstage_api_key, temperature=temperature)


@lru_cache
def get_llm(temperature: float = 0.0):
    """일반 텍스트 생성용 LLM. solar-pro-3 우선 호출, 실패 시 solar-pro-2로 자동 롤백."""
    settings = get_settings()
    primary = _build_chat(settings.llm_model_primary, temperature)
    fallback = _build_chat(settings.llm_model_fallback, temperature)
    return primary.with_fallbacks([fallback])


def get_structured_llm(schema: type[T], temperature: float = 0.0):
    """구조화 출력(JSON) 노드용. 두 모델 각각에 구조화 출력을 씌운 뒤 fallback을 연결한다."""
    settings = get_settings()
    primary = _build_chat(settings.llm_model_primary, temperature).with_structured_output(schema)
    fallback = _build_chat(settings.llm_model_fallback, temperature).with_structured_output(schema)
    return primary.with_fallbacks([fallback])
