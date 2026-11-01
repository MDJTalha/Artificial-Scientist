"""FastAPI application entry point."""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from artificial_scientist.api.routes.autonomy import router as autonomy_router
from artificial_scientist.api.routes.discovery import router as discovery_router
from artificial_scientist.api.routes.health import router as health_router
from artificial_scientist.api.routes.knowledge import router as knowledge_router
from artificial_scientist.api.routes.lab import router as lab_router
from artificial_scientist.api.routes.literature import router as literature_router
from artificial_scientist.api.routes.manuscripts import router as manuscripts_router
from artificial_scientist.api.routes.math_tools import router as math_tools_router
from artificial_scientist.api.routes.memory import router as memory_router
from artificial_scientist.api.routes.records import router as records_router
from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.config import get_settings

settings = get_settings()
LAB_RUN_BODY_LIMIT_BYTES = 64 * 1024
DISCOVERY_BODY_LIMIT_BYTES = 1024 * 1024


class Phase7RecordIsolationGateMiddleware:
    """Fail closed on shared research records until tenant-scoped access is implemented.

    Phase 6 tenant isolation currently protects lab runs and artifacts, not the general
    append-only research-record store. Production-like deployments must not expose those
    shared records or discovery endpoints until that store has tenant-scoped persistence
    and authorization. Local development remains available for implementation and testing.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        guarded_path = (
            path == "/api/v1/records"
            or path.startswith("/api/v1/records/")
            or path == "/api/v1/discovery"
            or path.startswith("/api/v1/discovery/")
        )
        if (
            scope.get("type") != "http"
            or not guarded_path
            or get_settings().environment.lower() == "development"
        ):
            await self.app(scope, receive, send)
            return

        import json

        body = json.dumps(
            {
                "detail": (
                    "Research records and discovery are disabled outside development "
                    "until tenant-scoped record authorization is implemented and reviewed."
                )
            },
            separators=(",", ":"),
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


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
                        if 400 <= status_code < 500
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
    """Bound computational and discovery request bodies before JSON parsing."""

    def __init__(self, app: ASGIApp, max_body_bytes: int = LAB_RUN_BODY_LIMIT_BYTES) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        is_lab_run_post = (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and path == "/api/v1/lab/runs"
        )
        is_discovery_post = (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and path.startswith("/api/v1/discovery/")
        )
        if not (is_lab_run_post or is_discovery_post):
            await self.app(scope, receive, send)
            return
        max_body_bytes = (
            DISCOVERY_BODY_LIMIT_BYTES if is_discovery_post else self.max_body_bytes
        )
        too_large_detail = (
            "Request body exceeds the endpoint size limit."
            if is_discovery_post
            else f"Lab run request body exceeds the {max_body_bytes}-byte limit."
        )

        headers = {
            key.lower(): value
            for key, value in scope.get("headers", [])
        }
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                await self._too_large(send, too_large_detail)
                return
            if declared_length < 0 or declared_length > max_body_bytes:
                await self._too_large(send, too_large_detail)
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
            if body_size > max_body_bytes:
                await self._too_large(send, too_large_detail)
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
    async def _too_large(send: Send, detail: str) -> None:
        import json

        body = json.dumps({"detail": detail}, separators=(",", ":")).encode("utf-8")
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
        "Research-first scientific system with traceable records, literature metadata, "
        "bounded mathematics, controlled computation, and structured hypothesis assessment. "
        "Automated truth verification and autonomous scientific discovery are not claimed."
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
app.include_router(autonomy_router)
app.include_router(discovery_router)
app.include_router(literature_router)
app.include_router(math_tools_router)
app.include_router(memory_router)
app.include_router(manuscripts_router)
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
