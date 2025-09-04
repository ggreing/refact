from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import thread, admin, ai_assist, postgre
from api.config.settings import settings
from shared.logging_config import configure_logging
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from api.middleware.error_handler import (
    unhandled_exception_middleware,
    http_exception_handler,
    validation_exception_handler,
)
# from . import rabbitmq
# from .db import ensure_indexes

app = FastAPI(
    # root_path="/api",
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug
)

configure_logging(service_name="api")



# ✅ CORS 설정
# 현재 "*"로 설정되어 있어 모든 출처(http, https 포함)에서의 접근을 허용합니다.
# 이는 개발 환경에서는 편리하지만, 운영 환경에서는 보안에 취약할 수 있습니다.
# 운영 시에는 아래와 같이 실제 프론트엔드 주소를 명시적으로 추가하는 것을 권장합니다.
# origins = [
#     "http://localhost:3000",
#     "https://your-production-domain.com",
#     "http://your-production-domain.com",
# ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용 (개발용)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 미들웨어/예외 핸들러 등록
app.middleware("http")(unhandled_exception_middleware)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 기본 헬스체크 추가
@app.get("/")
async def root():
    return {
        "message": f"{settings.app_name} is running",
        "version": settings.version,
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": ["api", "chat"],
        "version": settings.version
    }

# @app.on_event("startup")
# async def on_startup():
#     # RabbitMQ 토폴로지(큐/익스체인지) 보장
#     # The new rabbitmq.py uses a different pattern for topology declaration
#     conn = await rabbitmq.get_rabbitmq_connection()
#     async with conn:
#         ch = await conn.channel()
#         await rabbitmq.declare_topology(ch)
#     # Mongo 인덱스 보장(중복 정리 포함)
#     await ensure_indexes(settings.app_org_id)

# 라우터 등록 - thread, admin, ai_assist 활성화
app.include_router(thread.router, prefix="/api/v1/thread", tags=["Thread"])
app.include_router(postgre.router, prefix="/api/v1/postgre", tags=["Postgre"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(ai_assist.router, prefix="/api/v1", tags=["AI Assist"])

# 다른 라우터들 주석 처리
# app.include_router(galaxy.router, prefix="/galaxy", tags=["Galaxy Picks"])
# app.include_router(translate.router, prefix="/translate", tags=["translate"])
# app.include_router(files.router, prefix="/files", tags=["files"])
# app.include_router(events.router, prefix="/events", tags=["events"])
# app.include_router(sim.router, prefix="/sim", tags=["sim"])
# app.include_router(sales.router, prefix="/sales", tags=["sales"])
# app.include_router(misc.router, tags=["misc"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        #ssl_certfile="fullchain.crt",
        #ssl_keyfile="private.key"
    )