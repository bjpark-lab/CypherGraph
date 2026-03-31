"""
ClickHouse 스키마 조회 tool
"""
import json
import logging

from app.services.clickhouse_service import get_clickhouse_schema_info

logger = logging.getLogger(__name__)

TOOL_LABEL = "ClickHouse 스키마 조회"

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "clickhouse_schema_tool",
        "description": "ClickHouse 데이터베이스의 테이블 및 컬럼 구조를 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def run(args: dict) -> str:
    try:
        schema = get_clickhouse_schema_info()
        return json.dumps(schema, ensure_ascii=False)
    except Exception as e:
        logger.error(f"clickhouse_schema_tool 실패: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
