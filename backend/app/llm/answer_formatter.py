"""
최종 답변 formatter
Tool 결과를 사용자가 이해하기 쉬운 짧은 답변 구조로 정리한다.
"""
from __future__ import annotations

from app.schemas.chat import ToolResult


def format_final_answer(message: str, tool_result: ToolResult) -> str:
    base = (message or "").strip()
    summary = (tool_result.summary or "").strip()
    sources = tool_result.sources or []

    parts: list[str] = []

    if base:
        parts.append(base)
    elif summary:
        parts.append(summary)
    else:
        parts.append("데이터 조회는 완료됐지만 요약 문장을 충분히 만들지 못했습니다.")

    if summary and summary not in parts[0]:
        parts.append(f"근거 요약: {summary}")

    if sources:
        source_label = ", ".join(sources)
        parts.append(f"사용 소스: {source_label}")

    if not tool_result.graph and not tool_result.table and not tool_result.analytics:
        parts.append("조회 결과가 제한적이어서, 필요하면 조건을 더 구체화해 다시 질문하는 것이 좋습니다.")

    return "\n\n".join(parts).strip()
