"""
채팅 trace 메타데이터 유틸
질문 유형, 선택 소스, 호출 요약을 기록할 때 사용한다.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ChatTrace:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: float = field(default_factory=time.monotonic)
    question_type: str | None = None
    route_reason: str | None = None
    preferred_sources: list[str] = field(default_factory=list)

    def latency_ms(self) -> float:
        return (time.monotonic() - self.started_at) * 1000
