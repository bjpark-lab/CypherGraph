"""
그래프 관련 스키마 정의
"""
from pydantic import BaseModel, Field
from typing import Any


class GraphNode(BaseModel):
    id: str
    labels: list[str]
    properties: dict[str, Any]


class GraphEdge(BaseModel):
    id: str
    type: str
    source: str
    target: str
    properties: dict[str, Any]


class GraphResult(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    raw: list[dict[str, Any]] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    result: GraphResult
    cypher: str
    row_count: int
    execution_time_ms: float


class SchemaResponse(BaseModel):
    node_labels: list[str]
    relationship_types: list[str]
    # 기존 coordinator 소비자와의 하위 호환 필드
    properties: dict[str, list[str]]
    # 프런트엔드 런타임 스키마가 사용하는 명시적 필드
    node_properties: dict[str, list[str]]
    relationship_properties: dict[str, list[str]]
    raw_schema: str | None = None
