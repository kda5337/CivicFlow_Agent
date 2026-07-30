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


@lru_cache
def get_structured_llm(schema: type[T], temperature: float = 0.0):
    """구조화 출력(JSON) 노드용. 두 모델 각각에 구조화 출력을 씌운 뒤 fallback을 연결한다.

    ChatUpstage 생성 자체가 매번 1~2초 걸려서(내부적으로 클라이언트를 새로 구성하는 비용),
    get_llm처럼 캐싱하지 않으면 호출할 때마다 이 비용을 그대로 지불하게 된다.
    """
    settings = get_settings()
    primary = _build_chat(settings.llm_model_primary, temperature).with_structured_output(schema)
    fallback = _build_chat(settings.llm_model_fallback, temperature).with_structured_output(schema)
    return primary.with_fallbacks([fallback])
