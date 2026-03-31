"""
ClickHouse 연결 및 쿼리 실행 서비스
외부 ClickHouse 서버에 대한 읽기 전용 조회를 담당한다.
"""
import logging
import time
from typing import Any
from urllib.parse import urlparse, parse_qs

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from app.core.config import settings

logger = logging.getLogger(__name__)

_client_instance: Client | None = None


def _client_kwargs_from_settings() -> dict[str, Any]:
    """설정값으로부터 clickhouse-connect 클라이언트 인자를 구성한다."""
    if settings.clickhouse_uri:
        parsed = urlparse(settings.clickhouse_uri)
        query = parse_qs(parsed.query)
        port = parsed.port or (8443 if parsed.scheme == "https" else 8123)
        username = parsed.username or settings.clickhouse_user
        password = parsed.password or settings.clickhouse_password
        database = (parsed.path or "/").lstrip("/") or settings.clickhouse_database
        secure = parsed.scheme == "https"
        return {
            "host": parsed.hostname or "localhost",
            "port": port,
            "username": username,
            "password": password,
            "database": database,
            "secure": secure,
            "connect_timeout": settings.clickhouse_timeout,
            "send_receive_timeout": settings.clickhouse_timeout,
            "query_limit": settings.clickhouse_max_rows,
            **({"client_name": query.get("client_name", [None])[0]} if query.get("client_name") else {}),
        }

    return {
        "host": "localhost",
        "port": 8443 if settings.clickhouse_secure else 8123,
        "username": settings.clickhouse_user,
        "password": settings.clickhouse_password,
        "database": settings.clickhouse_database,
        "secure": settings.clickhouse_secure,
        "connect_timeout": settings.clickhouse_timeout,
        "send_receive_timeout": settings.clickhouse_timeout,
        "query_limit": settings.clickhouse_max_rows,
    }


def get_clickhouse_client() -> Client:
    """ClickHouse 클라이언트 싱글톤 반환"""
    global _client_instance
    if _client_instance is None:
        kwargs = _client_kwargs_from_settings()
        safe_kwargs = {k: v for k, v in kwargs.items() if k != "password"}
        logger.info(f"ClickHouse 클라이언트 초기화: {safe_kwargs}")
        _client_instance = clickhouse_connect.get_client(**kwargs)
    return _client_instance


def check_clickhouse_connection() -> bool:
    """ClickHouse 연결 상태 확인"""
    if not settings.clickhouse_uri and not settings.clickhouse_user:
        return False

    try:
        client = get_clickhouse_client()
        client.query("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"ClickHouse 연결 실패: {e}")
        return False


def execute_clickhouse_query(
    sql: str,
    params: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """ClickHouse SQL을 실행하고 JSON 직렬화 가능한 결과를 반환한다."""
    start = time.monotonic()
    client = get_clickhouse_client()
    result = client.query(sql, parameters=params or {})
    rows = [dict(zip(result.column_names, row)) for row in result.result_rows]
    elapsed_ms = (time.monotonic() - start) * 1000
    logger.debug(f"ClickHouse 쿼리 실행 완료 ({elapsed_ms:.1f}ms): {sql[:120]}")
    return rows, elapsed_ms


def get_clickhouse_schema_info() -> dict[str, Any]:
    """현재 데이터베이스의 테이블/컬럼 정보를 반환한다."""
    client = get_clickhouse_client()
    database = settings.clickhouse_database
    query = """
    SELECT
        table,
        name,
        type
    FROM system.columns
    WHERE database = %(database)s
    ORDER BY table, position
    """
    result = client.query(query, parameters={"database": database})

    tables: dict[str, list[dict[str, str]]] = {}
    for table_name, column_name, column_type in result.result_rows:
        tables.setdefault(table_name, []).append(
            {"name": column_name, "type": column_type}
        )

    return {
        "database": database,
        "tables": tables,
    }
