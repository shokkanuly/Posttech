"""Run as a separate service: uvicorn app.gateway.main:app --port 9000."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime
from sqlalchemy import func

from app.gateway.config import GatewaySettings
from app.gateway.connectors import TemporaryConnectorError
from app.gateway.models import GatewayJob
from app.gateway.runtime import GatewayRuntime, status_for
from app.integrations import signing
from app.integrations.contracts import (
    DocumentRequest,
    EmployeePage,
    EmployeeSnapshot,
    GatewayHealth,
    JobStatus,
    RecoveryCommand,
)
from app.middleware import RequestBodyLimitMiddleware

logger = logging.getLogger("janamen.gateway")


def create_app(config: GatewaySettings | None = None) -> FastAPI:
    runtime = GatewayRuntime(config or GatewaySettings())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime.initialize()
        stop = asyncio.Event()

        async def run():
            while not stop.is_set():
                try:
                    await asyncio.to_thread(runtime.tick)
                except Exception as exc:
                    logger.error("Gateway worker failure (%s)", type(exc).__name__)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=runtime.config.POLL_SECONDS)
                except TimeoutError:
                    pass

        task = asyncio.create_task(run()) if runtime.config.WORKER_ENABLED else None
        yield
        stop.set()
        if task:
            await task
        runtime.engine.dispose()

    app = FastAPI(
        title="JanaMen gateway — MOCK ONLY",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.runtime = runtime

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        body = await request.body()
        path = request.url.path + ("?" + request.url.query if request.url.query else "")
        try:
            nonce = signing.verify(
                request.headers, runtime.config.JANAMEN_KEYS, request.method, path, body
            )
            await asyncio.to_thread(runtime.remember_nonce, nonce)
        except (signing.SignatureError, HTTPException):
            return JSONResponse(
                status_code=401, content={"detail": "Invalid integration signature"}
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request, _error):
        # Pydantic's default error includes input values; do not echo HR payloads.
        return JSONResponse(status_code=422, content={"detail": "Invalid canonical input"})

    @app.exception_handler(Exception)
    async def unexpected(_request, error):
        logger.error("Gateway request failure (%s)", type(error).__name__)
        return JSONResponse(status_code=500, content={"detail": "Gateway unavailable"})

    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=65536)

    @app.post("/v1/documents", status_code=202, response_model=JobStatus)
    def documents(payload: DocumentRequest, request: Request):
        if request.headers.get("idempotency-key") != payload.idempotency_key:
            raise HTTPException(400, "Idempotency-Key must match the canonical request")
        return runtime.submit(payload)

    @app.get("/v1/documents/{idempotency_key}", response_model=JobStatus)
    def document_status(idempotency_key: str):
        with runtime.sessions() as db:
            job = db.query(GatewayJob).filter_by(idempotency_key=idempotency_key).first()
            if job is None:
                raise HTTPException(404, "Job not found")
            return status_for(job)

    @app.post("/v1/documents/{idempotency_key}/retry", response_model=JobStatus)
    def retry_document(idempotency_key: str, payload: RecoveryCommand):
        return runtime.retry(idempotency_key, payload)

    @app.get("/v1/employees", response_model=EmployeePage)
    def employees(updated_since: AwareDatetime | None = None):
        try:
            rows = runtime.one_c.employees(updated_since)
        except TemporaryConnectorError:
            raise HTTPException(503, "MOCK_1C_UNAVAILABLE") from None
        return EmployeePage(
            mode="MOCK", employees=rows, next_cursor=runtime.one_c.cursor(updated_since)
        )

    @app.get("/v1/employees/{employee_code}", response_model=EmployeeSnapshot)
    def employee(employee_code: str):
        try:
            found = next(
                (r for r in runtime.one_c.employees() if r.employee_code == employee_code), None
            )
        except TemporaryConnectorError:
            raise HTTPException(503, "MOCK_1C_UNAVAILABLE") from None
        if found is None:
            raise HTTPException(404, "MOCK employee not found")
        return found

    @app.get("/health", response_model=GatewayHealth)
    def health():
        with runtime.sessions() as db:
            return GatewayHealth(
                status="healthy",
                mode="MOCK",
                one_c="UNAVAILABLE" if runtime.config.MOCK_ONE_C_UNAVAILABLE else "MOCK",
                documentolog="MOCK"
                if runtime.config.MOCK_DOCUMENTOLOG_FAILURE == "none"
                else "UNAVAILABLE",
                pending_jobs=db.query(GatewayJob)
                .filter(GatewayJob.status.in_(["PENDING", "PROCESSING"]))
                .count(),
                pending_callbacks=db.query(GatewayJob).filter_by(callback_status="PENDING").count(),
                last_success=db.query(func.max(GatewayJob.updated_at))
                .filter_by(status="REGISTERED")
                .scalar(),
            )

    return app


app = create_app()
