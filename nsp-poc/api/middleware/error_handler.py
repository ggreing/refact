import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("api.error")

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("HTTPException", extra={"path": str(request.url), "status": exc.status_code})
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": {"code": exc.status_code, "message": exc.detail}})

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = exc.errors()
    logger.warning("ValidationError", extra={"path": str(request.url), "errors": details})
    return JSONResponse(status_code=422, content={"ok": False, "error": {"code": 422, "message": "Validation error", "details": details}})

async def unhandled_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("UnhandledError", extra={"path": str(request.url)})
        return JSONResponse(status_code=500, content={"ok": False, "error": {"code": 500, "message": "Internal server error"}})
