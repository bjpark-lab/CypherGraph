"""
ClickHouse SQL 안전성 검증 모듈
읽기 전용 SELECT 쿼리만 허용하고 결과 행 수를 제한한다.
"""
import re

from app.core.config import settings

FORBIDDEN_KEYWORDS = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bALTER\b",
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bOPTIMIZE\b",
    r"\bSYSTEM\b",
    r"\bCREATE\b",
    r"\bRENAME\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
]


class SQLGuardError(Exception):
    """SQL 안전성 검증 실패 예외"""
    pass


def validate_sql(sql: str) -> str:
    """SQL을 검증하고 LIMIT이 보장된 안전한 쿼리를 반환한다."""
    cleaned = sql.strip().rstrip(";")
    upper = cleaned.upper()

    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        raise SQLGuardError("복수 SQL 문은 허용되지 않습니다.")

    if not upper.startswith("SELECT") and not upper.startswith("WITH"):
        raise SQLGuardError("읽기 전용 SELECT/WITH 쿼리만 허용됩니다.")

    for pattern in FORBIDDEN_KEYWORDS:
        match = re.search(pattern, upper)
        if match:
            raise SQLGuardError(
                f"보안상 허용되지 않는 키워드가 포함되어 있습니다: {match.group()}"
            )

    if re.search(r"\bFORMAT\b", upper):
        raise SQLGuardError("FORMAT 지정은 허용되지 않습니다.")

    if not re.search(r"\bLIMIT\s+\d+\b", upper):
        cleaned = f"{cleaned} LIMIT {settings.clickhouse_max_rows}"

    return cleaned


def sanitize_sql_from_llm(sql: str) -> str:
    """LLM이 생성한 SQL에서 코드블록 등을 제거한 뒤 검증한다."""
    sql = re.sub(r"```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"^sql\s*\n", "", sql.strip(), flags=re.IGNORECASE)
    sql = sql.strip()
    return validate_sql(sql)
