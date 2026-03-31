"""
질문 분류용 pre-router
사용자 질문을 graph / analytics / hybrid / ambiguous로 분류한다.
"""
from __future__ import annotations

from dataclasses import dataclass


GRAPH_KEYWORDS = {
    "관계", "연결", "경로", "흐름", "거쳤", "upstream", "downstream",
    "recipe", "step", "노드", "edge", "그래프", "연관",
}

ANALYTICS_KEYWORDS = {
    "평균", "합계", "분포", "추세", "기간", "상위", "하위", "표준편차",
    "stddev", "variance", "histogram", "trend", "count", "집계", "비교",
    "최대", "최소", "최근", "증가", "감소",
}

HYBRID_HINTS = {
    "같이", "함께", "동시에", "비교해", "분포", "경로", "관계", "통계",
}


@dataclass
class RouteDecision:
    question_type: str
    reason: str
    preferred_sources: list[str]


def classify_question(message: str) -> RouteDecision:
    text = (message or "").lower()

    graph_hits = sum(1 for kw in GRAPH_KEYWORDS if kw.lower() in text)
    analytics_hits = sum(1 for kw in ANALYTICS_KEYWORDS if kw.lower() in text)
    hybrid_hits = sum(1 for kw in HYBRID_HINTS if kw.lower() in text)

    if graph_hits > 0 and analytics_hits > 0:
        return RouteDecision(
            question_type="hybrid",
            reason=f"graph={graph_hits}, analytics={analytics_hits} 키워드가 함께 감지됨",
            preferred_sources=["neo4j", "clickhouse"],
        )

    if hybrid_hits >= 2 and (graph_hits > 0 or analytics_hits > 0):
        return RouteDecision(
            question_type="hybrid",
            reason="복합 질의 표현이 감지됨",
            preferred_sources=["neo4j", "clickhouse"],
        )

    if graph_hits > 0:
        return RouteDecision(
            question_type="graph",
            reason=f"graph 키워드 {graph_hits}개 감지",
            preferred_sources=["neo4j"],
        )

    if analytics_hits > 0:
        return RouteDecision(
            question_type="analytics",
            reason=f"analytics 키워드 {analytics_hits}개 감지",
            preferred_sources=["clickhouse"],
        )

    return RouteDecision(
        question_type="ambiguous",
        reason="명확한 graph/analytics 키워드가 부족함",
        preferred_sources=[],
    )
