from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
from loguru import logger
import json
from pathlib import Path

from app.core.config import settings
from app.core.tracing import init_tracing
from app.api.v1 import crawl, summarize, audio

# 디버그 모드 (환경변수로 제어, 기본값: False)
import os
DEBUG_MODE = os.getenv("DEBUG_CORS", "false").lower() == "true"
DEBUG_LOG_PATH = Path(os.getenv("DEBUG_LOG_PATH", "/tmp/debug.log"))

def debug_log(hypothesis_id: str, location: str, message: str, data: dict):
    """디버그 로그를 NDJSON 형식으로 파일에 기록 (DEBUG_MODE일 때만)"""
    if not DEBUG_MODE:
        return
    import time
    log_entry = {
        "timestamp": int(time.time() * 1000),
        "sessionId": "debug-session",
        "runId": "cors-debug",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data
    }
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 프로덕션에서 로깅 실패해도 앱은 계속 동작


class DebugCORSMiddleware(BaseHTTPMiddleware):
    """CORS 요청을 디버깅하기 위한 미들웨어 (DEBUG_MODE일 때만 로깅)"""
    async def dispatch(self, request: Request, call_next):
        if DEBUG_MODE:
            origin = request.headers.get("origin", "NO_ORIGIN")
            method = request.method
            path = request.url.path
            
            debug_log("D", "main.py:DebugCORSMiddleware", "Request received", {
                "method": method,
                "path": path,
                "origin": origin,
                "is_options": method == "OPTIONS"
            })
        
        response = await call_next(request)
        
        if DEBUG_MODE:
            origin = request.headers.get("origin", "NO_ORIGIN")
            cors_header = response.headers.get("access-control-allow-origin", "NOT_SET")
            debug_log("D", "main.py:DebugCORSMiddleware:response", "Response headers", {
                "status_code": response.status_code,
                "cors_header": cors_header,
                "origin_requested": origin
            })
        
        return response


def get_application() -> FastAPI:
    # Phoenix LLMOps 트레이싱 초기화
    init_tracing()
    
    _app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="""
## Read-For-Me API

URL 크롤링, AI 요약, 뉴스 스크립트 생성 및 TTS 음성 합성을 제공하는 백엔드 API입니다.

### 주요 기능

- **🔍 Crawl**: URL을 입력받아 웹 페이지 콘텐츠를 크롤링하고 정제
- **📝 Summarize**: AI 기반 콘텐츠 요약 (Gemini)
- **🎙️ Audio**: 뉴스 스크립트 생성 및 TTS 음성 합성 (OpenAI)

### 지원 플랫폼

- GeekNews (`news.hada.io`)
- Medium (`medium.com`)
- 일반 웹사이트 (trafilatura 기반)

### 인증

현재 버전은 인증 없이 사용 가능합니다.
        """,
        openapi_url=None,  # 커스텀 엔드포인트 사용
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {
                "name": "crawl",
                "description": "URL 크롤링 및 콘텐츠 추출 API",
            },
            {
                "name": "summarize",
                "description": "AI 기반 콘텐츠 요약 API (Gemini)",
            },
            {
                "name": "audio",
                "description": "뉴스 스크립트 생성 및 TTS 음성 합성 API (OpenAI)",
            },
        ],
        contact={
            "name": "Read-For-Me Team",
            "url": "https://github.com/your-repo/read-for-me",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    # CORS origins 설정
    raw_origins = settings.BACKEND_CORS_ORIGINS
    cors_origins = [str(origin) for origin in raw_origins]
    
    if DEBUG_MODE:
        debug_log("A", "main.py:get_application", "CORS origins analysis", {
            "raw_origins": [str(o) for o in raw_origins],
            "cors_origins": cors_origins,
            "has_trailing_slash": [o.endswith("/") for o in cors_origins],
            "expected_browser_origin": "http://localhost:3000"
        })
    
    logger.info(f"CORS 허용 origins: {cors_origins}")
    
    # trailing slash 제거 (정규화)
    cors_origins_normalized = [o.rstrip("/") for o in cors_origins]
    if DEBUG_MODE:
        debug_log("A", "main.py:get_application:normalized", "Normalized origins", {
            "before": cors_origins,
            "after": cors_origins_normalized
        })
    
    if cors_origins_normalized:
        _app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins_normalized,  # 정규화된 origins 사용
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info(f"CORS 미들웨어 활성화됨 (정규화된 origins: {cors_origins_normalized})")
        
        if DEBUG_MODE:
            debug_log("C", "main.py:get_application:middleware", "CORS middleware added", {
                "allow_origins": cors_origins_normalized,
                "allow_methods": ["*"],
                "allow_headers": ["*"]
            })
    else:
        logger.warning("CORS origins가 설정되지 않음 - CORS 미들웨어 비활성화")

    # 디버그 미들웨어 (DEBUG_MODE일 때만 유용하지만 항상 추가 - 오버헤드 최소)
    _app.add_middleware(DebugCORSMiddleware)

    # API v1 라우터 등록
    _app.include_router(crawl.router, prefix=settings.API_V1_STR)
    _app.include_router(summarize.router, prefix=settings.API_V1_STR)
    _app.include_router(audio.router, prefix=settings.API_V1_STR)

    return _app


app = get_application()

# Swagger UI / ReDoc이 OpenAPI 스펙을 찾을 수 있도록 URL 설정
app.openapi_url = f"{settings.API_V1_STR}/openapi.json"


# ============================================================================
# 커스텀 OpenAPI 엔드포인트 (UTF-8 인코딩 지원)
# ============================================================================

@app.get(f"{settings.API_V1_STR}/openapi.json", include_in_schema=False)
async def custom_openapi():
    """
    UTF-8 인코딩된 OpenAPI 스펙을 반환합니다.
    기본 FastAPI OpenAPI 엔드포인트의 한글 깨짐 문제를 해결합니다.
    """
    openapi_schema = app.openapi()
    return Response(
        content=json.dumps(openapi_schema, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
    )


# Health Check
@app.get("/")
async def root():
    return {
        "message": "Welcome to Read-For-Me API",
        "version": settings.VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 디버깅 용: python app/main.py로 실행 시
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
