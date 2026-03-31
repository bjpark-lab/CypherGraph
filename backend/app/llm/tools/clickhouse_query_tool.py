"""
ClickHouse SQL 생성·실행 tool
자연어 질문을 SQL로 변환한 뒤 ClickHouse에서 실행한다.
"""
import json
import logging

from langchain_core.prompts import PromptTemplate

from app.core.config import settings
from app.llm.models import get_sql_llm
from app.llm.prompts import CLICKHOUSE_SQL_GENERATION_PROMPT
from app.services.clickhouse_service import execute_clickhouse_query, get_clickhouse_schema_info
from app.services.sql_guard import sanitize_sql_from_llm, SQLGuardError

logger = logging.getLogger(__name__)

TOOL_LABEL = "ClickHouse 조회"

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "clickhouse_query_tool",
        "description": (
            "자연어 질문을 ClickHouse SQL로 변환하고 실행하여 집계/추세/분포 데이터를 반환합니다. "
            "평균, 합계, 분포, 추세, 기간별 변화, chamber/lot/wafer별 집계 질문에 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "분석하고자 하는 자연어 질문 (한글 또는 영어)",
                }
            },
            "required": ["question"],
        },
    },
}


def _schema_text() -> str:
    schema = get_clickhouse_schema_info()
    lines: list[str] = [f"데이터베이스: {schema.get('database', '')}"]
    tables = schema.get("tables", {})
    for table_name, columns in tables.items():
        col_desc = ", ".join(f"{c['name']} ({c['type']})" for c in columns)
        lines.append(f"- {table_name}: {col_desc}")
    return "\n".join(lines)


def run(args: dict) -> str:
    question: str = args.get("question", "")
    try:
        prompt = PromptTemplate.from_template(CLICKHOUSE_SQL_GENERATION_PROMPT).format(
            schema=_schema_text(),
            max_rows=settings.clickhouse_max_rows,
            question=question,
        )
        sql = get_sql_llm().invoke(prompt).content
        if isinstance(sql, list):
            sql = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in sql
            )

        sql = sanitize_sql_from_llm(str(sql))
        rows, elapsed_ms = execute_clickhouse_query(sql)

        summary = f"ClickHouse에서 {len(rows)}건 조회"
        if not rows:
            summary = "ClickHouse 조회 결과가 없습니다."

        return json.dumps(
            {
                "sql": sql,
                "result": rows,
                "row_count": len(rows),
                "execution_time_ms": elapsed_ms,
                "summary": summary,
                "source": "clickhouse",
            },
            ensure_ascii=False,
        )
    except SQLGuardError as e:
        logger.warning(f"clickhouse_query_tool SQL 검증 실패: {e}")
        return json.dumps({"error": str(e), "sql": "", "result": []}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"clickhouse_query_tool 실패: {e}")
        return json.dumps({"error": str(e), "sql": "", "result": []}, ensure_ascii=False)
