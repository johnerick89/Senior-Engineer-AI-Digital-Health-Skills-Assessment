from __future__ import annotations

import uuid
from decimal import Decimal

from app.core.logging import log_event


class CaptureLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, object]]] = []

    def info(self, event: str, **payload: object) -> None:
        self.messages.append((event, payload))


def test_log_event_serializes_decimal_and_uuid() -> None:
    logger = CaptureLogger()
    thread_id = uuid.UUID("12345678-1234-5678-1234-567812345678")

    log_event(
        logger,
        "chat.completed",
        thread_id=thread_id,
        estimated_cost_usd=Decimal("0.00123"),
    )

    event, payload = logger.messages[0]
    assert event == "chat.completed"
    assert payload["thread_id"] == str(thread_id)
    assert payload["estimated_cost_usd"] == 0.00123
