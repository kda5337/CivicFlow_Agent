import re

import psycopg2

from app.core.config import get_settings
from app.core.llm import get_structured_llm
from app.core.tracing import get_langfuse_client
from app.graph.prompts import CURRICULUM_SQL_PROMPT
from app.graph.state import InquiryState
from app.models.schemas import CurriculumSQLQuery

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|call|copy|merge)\b",
    re.IGNORECASE,
)


def _is_safe_select(sql: str) -> bool:
    """LLM이 생성한 SQL이 데이터를 바꾸지 않는 단일 SELECT 문인지 확인한다."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped or not re.match(r"(?is)^select\b", stripped):
        return False
    if ";" in stripped or _FORBIDDEN_KEYWORDS.search(stripped):
        return False
    return True


def _run_query(sql: str) -> str:
    settings = get_settings()
    conn = psycopg2.connect(settings.supabase_database_url)
    try:
        # 정규식 검사를 통과했더라도, DB 세션 자체를 읽기 전용으로 열어 이중으로 방어한다.
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return "(조회된 데이터 없음)"
    lines = [", ".join(columns)]
    lines += [", ".join(str(value) for value in row) for row in rows]
    return "\n".join(lines)


def _format_evidence(sql: str, query_result: str) -> str:
    # generate_node가 결과값만 보고 "어떤 조건으로 조회했는지" 맥락을 잃지 않도록,
    # 실행한 SQL 자체도 근거에 함께 남긴다.
    return f"(실행한 SQL)\n{sql}\n\n(조회 결과 - 이미 문의 조건으로 필터링된 데이터임)\n{query_result}"


def curriculum_lookup_node(state: InquiryState) -> dict:
    """졸업요건_문의/교육과정_문의 Rule에 걸린 문의를, LLM이 생성한 SQL로 Supabase에서 직접 조회해 근거로 만든다."""
    llm = get_structured_llm(CurriculumSQLQuery)
    text = state["raw_text"]

    with get_langfuse_client().start_as_current_observation(
        name="curriculum-sql-lookup",
        as_type="tool",
        input={"text": text},
    ) as span:
        query: CurriculumSQLQuery = llm.invoke(CURRICULUM_SQL_PROMPT.format(text=text))
        sql = query.sql

        if not _is_safe_select(sql):
            content = "(생성된 SQL이 안전한 조회문이 아니라 실행하지 않음)"
        else:
            try:
                content = _format_evidence(sql, _run_query(sql))
            except Exception as error:
                content = f"(DB 조회 실패: {error})"

        span.update(output={"sql": sql, "result_preview": content[:500]})

    return {
        "retrieved_docs": [
            {"content": content, "source": "curriculum_db(SQL)", "score": 1.0}
        ]
    }
