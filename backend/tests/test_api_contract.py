from types import SimpleNamespace
from typing import cast
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import chat as chat_routes
from app.api.routes import graph as graph_routes
from app.main import app
from app.schemas.graph import QueryRequest
from app.services.neo4j_service import get_schema_info


class SchemaContractTests(unittest.TestCase):
    @patch("app.services.neo4j_service.get_graph")
    def test_schema_info_exposes_node_and_relationship_properties(self, get_graph: Mock) -> None:
        graph = SimpleNamespace(
            refresh_schema=Mock(),
            get_structured_schema={
                "node_props": {
                    "Wafer": [{"property": "wafer_id"}],
                },
                "rel_props": {
                    "PROCESSED_BY": [{"property": "started_at"}],
                },
                "relationships": [{"type": "PROCESSED_BY"}],
            },
            schema="(Wafer)-[:PROCESSED_BY]->(Recipe)",
        )
        get_graph.return_value = graph

        result = get_schema_info()

        self.assertEqual(result["node_properties"], {"Wafer": ["wafer_id"]})
        self.assertEqual(
            result["relationship_properties"],
            {"PROCESSED_BY": ["started_at"]},
        )
        self.assertEqual(result["properties"], result["node_properties"])

    def test_query_execution_time_is_required_number_in_openapi(self) -> None:
        schema = app.openapi()["components"]["schemas"]["QueryResponse"]

        self.assertIn("execution_time_ms", schema["required"])
        self.assertEqual(
            schema["properties"]["execution_time_ms"]["type"],
            "number",
        )


class SafeErrorResponseTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.api.routes.graph.execute_query")
    @patch("app.api.routes.graph.validate_query", return_value="MATCH (n) RETURN n")
    async def test_graph_query_hides_internal_exception(
        self,
        _validate_query: Mock,
        execute_query: Mock,
    ) -> None:
        execute_query.side_effect = RuntimeError("neo4j://private-host secret-token")

        with self.assertLogs("app.api.routes.graph", level="ERROR"), self.assertRaises(
            HTTPException
        ) as raised:
            await graph_routes.run_graph_query(QueryRequest(query="MATCH (n) RETURN n"))

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(raised.exception.detail, "쿼리 실행 중 오류가 발생했습니다.")
        self.assertNotIn("private-host", raised.exception.detail)
        self.assertNotIn("secret-token", raised.exception.detail)

    @patch("app.api.routes.graph.get_schema_info")
    async def test_graph_schema_hides_internal_exception(self, get_schema_info: Mock) -> None:
        get_schema_info.side_effect = RuntimeError("neo4j-password=secret")

        with self.assertLogs("app.api.routes.graph", level="ERROR"), self.assertRaises(
            HTTPException
        ) as raised:
            await graph_routes.get_graph_schema()

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(raised.exception.detail, "스키마 조회 중 오류가 발생했습니다.")
        self.assertNotIn("secret", raised.exception.detail)

    @patch("app.api.routes.chat.run_coordinator", new_callable=AsyncMock)
    async def test_chat_hides_internal_exception(self, run_coordinator: AsyncMock) -> None:
        run_coordinator.side_effect = RuntimeError("provider-key=secret")
        request = chat_routes.ChatRequestWithConversation(message="테스트")

        with self.assertLogs("app.api.routes.chat", level="ERROR"), self.assertRaises(
            HTTPException
        ) as raised:
            await chat_routes.chat(
                request,
                user=None,
                db=cast(AsyncSession, None),
            )

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(raised.exception.detail, "채팅 처리 중 오류가 발생했습니다.")
        self.assertNotIn("secret", raised.exception.detail)

    async def test_chat_stream_hides_internal_exception(self) -> None:
        async def failing_stream(**_kwargs):
            if False:
                yield ""
            raise RuntimeError("provider-key=stream-secret")

        request = chat_routes.ChatRequestWithConversation(message="테스트")
        with patch("app.api.routes.chat.stream_coordinator", failing_stream):
            with self.assertLogs("app.api.routes.chat", level="ERROR"):
                response = await chat_routes.chat_stream(
                    request,
                    user=None,
                    db=cast(AsyncSession, None),
                )
                chunks = [chunk async for chunk in response.body_iterator]

        def chunk_text(chunk: str | bytes | memoryview) -> str:
            if isinstance(chunk, str):
                return chunk
            return bytes(chunk).decode()

        body = "".join(chunk_text(chunk) for chunk in chunks)
        self.assertIn("채팅 스트리밍 중 오류가 발생했습니다.", body)
        self.assertNotIn("stream-secret", body)
        self.assertTrue(body.endswith("data: [DONE]\n\n"))


if __name__ == "__main__":
    unittest.main()
