"""FastAPI application entry point."""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from artificial_scientist.api.routes.health import router as health_router
from artificial_scientist.api.routes.knowledge import router as knowledge_router
from artificial_scientist.api.routes.lab import router as lab_router
from artificial_scientist.api.routes.literature import router as literature_router
from artificial_scientist.api.routes.math_tools import router as math_tools_router
from artificial_scientist.api.routes.records import router as records_router
from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.config import get_settings

settings = get_settings()
LAB_RUN_BODY_LIMIT_BYTES = 64 * 1024


class LabSecurityAuditMiddleware:
    """Persist final outcomes for tenant-scoped lab requests without logging payloads."""

    def __init__(self, app: ASGIApp, database_path: str) -> None:
        self.app = app
        self.database_path = database_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        is_lab_request = (
            scope["type"] == "http"
            and scope.get("path", "").startswith("/api/v1/lab/")
        )
        if not is_lab_request:
            await self.app(scope, receive, send)
            return

        audit_blocked = False

        async def audited_send(message: Message) -> None:
            nonlocal audit_blocked
            if audit_blocked:
                return
            if message["type"] == "http.response.start":
                state = scope.get("state") or {}
                context = state.get("authorization_audit")
                status_code = int(message["status"])
                # Authentication can fail before tenant authorization builds its
                # richer context. Record those outcomes as anonymous request events.
                if context is None and status_code in {401, 403, 503}:
                    context = {
                        "principal_id": None,
                        "tenant_id": None,
                        "action": "authentication:request",
                        "target_type": "request",
                        "target_id": None,
                        "correlation_id": (
                            scope.get("headers", [])
                            and next(
                                (
                                    value.decode("latin-1")
                                    for key, value in scope.get("headers", [])
                                    if key.lower() == b"x-correlation-id"
                                    and len(value) <= 128
                                ),
                                None,
                            )
                        ) or str(uuid4()),
                        "method": scope.get("method", "UNKNOWN"),
                        "route": scope.get("path", "")[:512],
                        "database_path": state.get(
                            "security_audit_database_path", self.database_path
                        ),
                    }
                if context:
                    outcome = (
                        "denied"
                        if status_code in {401, 403, 404}
                        else "failed"
                        if status_code >= 500
                        else "allowed"
                    )
                    try:
                        TenantDirectory(context.get("database_path", self.database_path)).audit(
                            principal_id=context.get("principal_id"),
                            tenant_id=context.get("tenant_id"),
                            action=context["action"],
                            target_type=context["target_type"],
                            target_id=context.get("target_id"),
                            outcome=outcome,
                            correlation_id=context.get("correlation_id"),
                            metadata={
                                "method": context["method"],
                                "route": context["route"],
                                "http_status": status_code,
                            },
                        )
                    except Exception:
                        # Do not return a success response when required audit persistence
                        # is unavailable. The original response has not been sent yet.
                        body = b'{"detail":"Security audit persistence is unavailable."}'
                        audit_blocked = True
                        await send(
                            {
                                "type": "http.response.start",
                                "status": 503,
                                "headers": [
                                    (b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode("ascii")),
                                ],
                            }
                        )
                        await send({"type": "http.response.body", "body": body})
                        return
            await send(message)

        await self.app(scope, receive, audited_send)


class LabRequestBodyLimitMiddleware:
    """Bound lab-run request bodies before JSON parsing and model validation."""

    def __init__(self, app: ASGIApp, max_body_bytes: int = LAB_RUN_BODY_LIMIT_BYTES) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        is_lab_run_post = (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") == "/api/v1/lab/runs"
        )
        if not is_lab_run_post:
            await self.app(scope, receive, send)
            return

        headers = {
            key.lower(): value
            for key, value in scope.get("headers", [])
        }
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                await self._too_large(send)
                return
            if declared_length < 0 or declared_length > self.max_body_bytes:
                await self._too_large(send)
                return

        body_chunks: list[bytes] = []
        body_size = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            body_size += len(chunk)
            if body_size > self.max_body_bytes:
                await self._too_large(send)
                return
            body_chunks.append(chunk)
            more_body = message.get("more_body", False)

        chunk_index = 0

        async def replay_body() -> Message:
            nonlocal chunk_index
            if chunk_index < len(body_chunks):
                chunk = body_chunks[chunk_index]
                chunk_index += 1
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": chunk_index < len(body_chunks),
                }
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_body, send)

    @staticmethod
    async def _too_large(send: Send) -> None:
        body = b'{"detail":"Lab run request body exceeds the 65536-byte limit."}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Research-first software foundation. Scientific research engines and "
        "autonomous discovery capabilities are not implemented yet."
    ),
)
app.add_middleware(LabRequestBodyLimitMiddleware)
app.add_middleware(LabSecurityAuditMiddleware, database_path=settings.database_path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(literature_router)
app.include_router(math_tools_router)
app.include_router(lab_router)
app.include_router(knowledge_router)
app.include_router(records_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Identify this API without overstating the current implementation."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }
