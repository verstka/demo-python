"""ASGI middleware: log HTTP request/response headers and body previews to stdout when DEBUG is on."""

from __future__ import annotations

import logging
import sys
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_MAX_BODY_LOG_BYTES = 16 * 1024

_logger = logging.getLogger("app.debug_http")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[DEBUG] %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def _header_lines(raw_headers: list[tuple[bytes, bytes]]) -> list[str]:
    lines: list[str] = []
    for key, value in raw_headers:
        k = key.decode("latin-1", errors="replace")
        v = value.decode("latin-1", errors="replace")
        lines.append(f"  {k}: {v}")
    return lines


def _body_preview(data: bytes, limit: int = _MAX_BODY_LOG_BYTES) -> tuple[str, bool]:
    truncated = len(data) > limit
    chunk = data[:limit]
    text = chunk.decode("utf-8", errors="replace")
    if truncated:
        text += f"\n  ... [{len(data) - limit} more bytes omitted]"
    return text, truncated


async def _drain_request_messages(receive: Receive) -> list[Message]:
    """Read all http.request chunks until body complete or disconnect."""
    messages: list[Message] = []
    while True:
        msg = await receive()
        messages.append(msg)
        if msg["type"] == "http.disconnect":
            break
        if msg["type"] == "http.request":
            if not msg.get("more_body", False):
                break
    return messages


def _request_body_from_messages(messages: list[Message]) -> bytes:
    parts: list[bytes] = []
    for msg in messages:
        if msg["type"] == "http.request":
            parts.append(msg.get("body", b""))
    return b"".join(parts)


class DebugRequestLoggingMiddleware:
    """Pure ASGI middleware: buffers request body for replay, logs request/response to stdout."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        buffered = await _drain_request_messages(receive)
        idx = 0

        async def replay_receive() -> Message:
            nonlocal idx
            if idx < len(buffered):
                out = buffered[idx]
                idx += 1
                return out
            return {"type": "http.disconnect"}

        method = scope.get("method", "")
        path_val = scope.get("path", "")
        if isinstance(path_val, bytes):
            path_s = path_val.decode("utf-8", errors="replace")
        else:
            path_s = str(path_val)
        query = scope.get("query_string", b"")
        if isinstance(query, (bytes, bytearray)):
            q = query.decode("utf-8", errors="replace")
        else:
            q = str(query)
        full_path = f"{path_s}?{q}" if q else path_s

        req_body = _request_body_from_messages(buffered)
        preview, trunc = _body_preview(req_body)

        _logger.info("---- request ----")
        _logger.info("%s %s", method, full_path)
        for line in _header_lines(list(scope.get("headers", []))):
            _logger.info(line)
        _logger.info("body (%s bytes)%s:", len(req_body), " [log truncated]" if trunc else "")
        for line in preview.splitlines():
            _logger.info("  %s", line)

        response_log_buf = bytearray()
        response_total_size = 0
        saw_response_start = False

        async def logging_send(message: Message) -> None:
            nonlocal saw_response_start, response_total_size
            if message["type"] == "http.response.start":
                saw_response_start = True
                response_log_buf.clear()
                response_total_size = 0
                status = message.get("status", 0)
                headers = list(message.get("headers", []))
                _logger.info("---- response ----")
                _logger.info("status %s", status)
                for line in _header_lines(headers):
                    _logger.info(line)
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if isinstance(chunk, memoryview):
                    chunk = chunk.tobytes()
                response_total_size += len(chunk)
                room = _MAX_BODY_LOG_BYTES - len(response_log_buf)
                if room > 0:
                    response_log_buf.extend(chunk[:room])
                if not message.get("more_body", False) and saw_response_start:
                    rtrunc = response_total_size > len(response_log_buf)
                    rpreview, _ = _body_preview(bytes(response_log_buf), _MAX_BODY_LOG_BYTES)
                    _logger.info(
                        "body (total %s bytes, preview up to %s)%s:",
                        response_total_size,
                        _MAX_BODY_LOG_BYTES,
                        " [log truncated]" if rtrunc else "",
                    )
                    for line in rpreview.splitlines():
                        _logger.info("  %s", line)
            await send(message)

        await self.app(scope, replay_receive, logging_send)
