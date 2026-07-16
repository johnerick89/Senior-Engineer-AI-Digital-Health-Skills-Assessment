"""Request/response logging middleware."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.logging import get_logger, log_event

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log inbound requests and outbound responses without body content."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Log request received and response completed with timing."""
        method = request.method
        path = request.url.path
        trace_id = (
            request.headers.get("X-Trace-Id")
            or request.headers.get("X-Request-Id")
            or str(uuid.uuid4())
        )
        bind_contextvars(trace_id=trace_id, method=method, path=path)
        log_event(
            logger,
            "request.received",
            event="request.received",
            method=method,
            path=path,
            trace_id=trace_id,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_event(
                logger,
                "request.completed",
                event="request.completed",
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                trace_id=trace_id,
            )
            return response
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_event(
                logger,
                "request.failed",
                event="request.failed",
                method=method,
                path=path,
                duration_ms=duration_ms,
                trace_id=trace_id,
                error=str(exc),
            )
            raise
        finally:
            clear_contextvars()
