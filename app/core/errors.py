from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ValidationFailure(ValueError):
    """Error de entrada que debe exponerse como 400 con el contrato de la API."""


class DataLoadError(RuntimeError):
    """La fuente de datos no pudo prepararse de forma segura."""


def utc_timestamp() -> str:
    """Timestamp UTC ISO-8601 con nueve dígitos fraccionarios y sufijo Z."""

    value = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    return value.replace("+00:00", "000Z")


def error_payload(request: Request, status: int, detail: str) -> dict[str, object]:
    if status == 400:
        title = "Bad Request"
        code = "VF"
        label = "Validación Fallida"
    else:
        status = 500
        title = "Internal Server Error"
        code = "IE"
        label = "Error Interno"

    return {
        "detail": detail,
        "instance": request.url.path,
        "status": status,
        "title": title,
        "type": (
            "https://developer.mozilla.org/es/docs/Web/HTTP/Reference/Status/"
            f"{status}"
        ),
        "timestamp": utc_timestamp(),
        "errorCode": code,
        "errorLabel": label,
        "method": request.method,
    }


def _validation_detail(exc: RequestValidationError) -> str:
    first = exc.errors()[0] if exc.errors() else None
    if not first:
        return "La solicitud no cumple el formato esperado"
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    message = first.get("msg", "valor inválido")
    return f"Solicitud inválida en '{location or 'body'}': {message}"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationFailure)
    async def validation_failure_handler(
        request: Request, exc: ValidationFailure
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content=error_payload(request, 400, str(exc)))

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_payload(request, 400, _validation_detail(exc)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        status = 400 if exc.status_code < 500 else 500
        return JSONResponse(
            status_code=status,
            content=error_payload(request, status, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_payload(
                request, 500, "Error interno al calcular las estadísticas de ventas"
            ),
        )
