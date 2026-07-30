"""Langfuse 트레이싱 초기화.

주의(순서): 이 모듈은 반드시 `load_dotenv()`가 실행된 *이후*에 import 되어야 한다.
Langfuse 클라이언트는 생성 시점에 LANGFUSE_PUBLIC_KEY/SECRET_KEY/BASE_URL을
os.environ에서 읽으므로, 그 전에 import/초기화되면 잘못된(또는 빈) 자격증명으로
클라이언트가 굳어버린다. 진입점(app/main.py)에서 dotenv 로드 -> init_tracing() ->
나머지 앱 import 순서를 지킨다.
"""

import re
from functools import lru_cache
from typing import Optional

from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler
from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch

# 한글은 Python 정규식에서 \w(단어 문자)로 취급되어, 공백 없이 한글이 바로 붙는
# "010-1234-5678로 연락주세요" 같은 실제 민원 문장에서 \b 경계가 깨져 마스킹이
# 누락된다. 그래서 \b 대신 ASCII 문자 클래스와 숫자 lookaround로 경계를 판단한다.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")


def _mask_otel_spans(*, params: MaskOtelSpansParams) -> Optional[MaskOtelSpansResult]:
    """민원 원문·답변초안에 포함될 수 있는 이메일/휴대폰번호를 export 시점에 마스킹한다."""
    patches: dict = {}

    for identifier, span in params.spans.items():
        replacements = {}
        for key, value in span.attributes.items():
            if not isinstance(value, str):
                continue
            masked = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
            masked = _PHONE_RE.sub("[REDACTED_PHONE]", masked)
            if masked != value:
                replacements[key] = masked
        if replacements:
            patches[identifier] = OtelSpanPatch(set_attributes=replacements)

    return MaskOtelSpansResult(span_patches=patches) if patches else None


@lru_cache
def init_tracing() -> Langfuse:
    """앱 시작 시 1회 호출. 마스킹이 적용된 전역 Langfuse 클라이언트를 등록한다.

    이후 어디서든 get_client()/CallbackHandler()를 호출하면 이 인스턴스를 재사용한다.
    """
    return Langfuse(mask_otel_spans=_mask_otel_spans)


def get_langfuse_client() -> Langfuse:
    return get_client()


@lru_cache
def get_langfuse_handler() -> CallbackHandler:
    """LangGraph/LangChain 실행에 붙일 콜백 핸들러. 프로세스당 한 번만 생성해 재사용한다."""
    return CallbackHandler()