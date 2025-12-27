"""
Summarize API Endpoint

콘텐츠 요약 API를 제공합니다.
SSE 스트리밍 엔드포인트 포함.
"""

import hashlib
import json
import time
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.services.storage import get_storage_service
from app.services.summary import SummaryService, get_summary_service

router = APIRouter(prefix="/summarize", tags=["summarize"])

# 기본 사용자 ID (프로토타입용)
DEFAULT_USER_ID = "default"


# ============================================================================
# Request/Response Schemas
# ============================================================================


class SummarizeRequest(BaseModel):
    """요약 요청 스키마"""

    content: str = Field(
        ...,
        min_length=10,
        description="요약할 콘텐츠 텍스트",
    )
    original_content: str | None = Field(
        None,
        description="원본 외부 링크 콘텐츠 (GeekNews 등). 있으면 content와 병합하여 요약",
    )
    url: str | None = Field(
        None,
        description="원본 URL (캐싱용, 선택)",
    )
    article_id: str | None = Field(
        None,
        description="아티클 ID (저장용, 선택). 없으면 URL 또는 content 해시 기반 자동 생성",
    )
    user_id: str | None = Field(
        None,
        description="사용자 ID (선택). 없으면 기본값 'default' 사용",
    )


class SummarizeResponse(BaseModel):
    """요약 응답 스키마"""

    bullet_points: list[str] = Field(
        ...,
        description="핵심 포인트 요약 (3-5개)",
    )
    main_topic: str = Field(
        ...,
        description="주요 주제 한 줄 요약",
    )
    model: str = Field(
        ...,
        description="사용된 모델 이름",
    )
    processing_time_ms: int = Field(
        ...,
        description="처리 시간 (밀리초)",
    )
    article_id: str = Field(
        ...,
        description="아티클 ID",
    )
    saved_path: str | None = Field(
        None,
        description="저장된 파일 경로 (저장 실패 시 None)",
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _generate_article_id(url: str | None, content: str) -> str:
    """
    URL 또는 content 해시 기반으로 article_id를 생성합니다.

    Args:
        url: 원본 URL (있으면 URL 기반 해시)
        content: 콘텐츠 텍스트 (URL 없으면 content 기반 해시)

    Returns:
        생성된 article_id
    """
    if url:
        # URL 기반 해시 (앞 8자리)
        hash_input = url
    else:
        # content 기반 해시 (앞 8자리)
        hash_input = content[:500]  # 앞 500자만 사용

    hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"summary_{hash_value}"


async def _save_summary_result(
    article_id: str,
    result: dict,
    user_id: str = DEFAULT_USER_ID,
    url: str | None = None,
) -> str | None:
    """
    요약 결과를 저장합니다 (StorageService 사용).

    저장 경로: users/{user_id}/summary/{article_id}_{timestamp}.json

    Args:
        article_id: 아티클 ID
        result: 요약 결과 딕셔너리
        user_id: 사용자 ID
        url: 원본 URL (메타데이터용)

    Returns:
        저장된 경로 (실패 시 None)
    """
    try:
        storage = get_storage_service()

        # 파일명 생성
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"{article_id}_{timestamp}.json"

        # 저장 경로
        path = f"users/{user_id}/summary/{filename}"

        # 저장할 데이터 구성
        save_data = {
            "user_id": user_id,
            "article_id": article_id,
            "url": url,
            "created_at": datetime.now().isoformat(),
            **result,
        }

        # JSON 저장
        saved_path = await storage.save_json(path, save_data)

        logger.info(f"요약 결과 저장됨: {saved_path}")
        return saved_path

    except Exception as e:
        logger.error(f"요약 결과 저장 실패: {e}")
        return None


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("", response_model=SummarizeResponse)
async def summarize_content(request: SummarizeRequest) -> SummarizeResponse:
    """
    콘텐츠를 요약합니다.

    - **content**: 요약할 텍스트 콘텐츠 (최소 10자)
    - **url**: 원본 URL (선택, 캐싱용)
    - **article_id**: 아티클 ID (선택, 저장용). 없으면 자동 생성
    - **user_id**: 사용자 ID (선택). 없으면 기본값 'default' 사용

    ## 저장 경로
    - `data/users/{user_id}/summary/{article_id}_{timestamp}.json`

    Returns:
        요약 결과 (bullet_points, main_topic, model, processing_time_ms, article_id, saved_path)
    """
    start_time = time.time()

    # user_id 및 article_id 결정
    user_id = request.user_id or DEFAULT_USER_ID
    article_id = request.article_id or _generate_article_id(
        request.url, request.content
    )

    try:
        service = get_summary_service()
        result = await service.summarize(
            content=request.content,
            original_content=request.original_content,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # 요약 결과 저장
        result_dict = {
            "bullet_points": result.bullet_points,
            "main_topic": result.main_topic,
            "model": service.model_name,
            "processing_time_ms": processing_time_ms,
        }
        saved_path = await _save_summary_result(
            article_id=article_id,
            result=result_dict,
            user_id=user_id,
            url=request.url,
        )

        logger.info(
            f"요약 API 완료: {len(result.bullet_points)}개 포인트, "
            f"처리시간={processing_time_ms}ms, article_id={article_id}, user_id={user_id}"
        )

        return SummarizeResponse(
            bullet_points=result.bullet_points,
            main_topic=result.main_topic,
            model=service.model_name,
            processing_time_ms=processing_time_ms,
            article_id=article_id,
            saved_path=str(saved_path) if saved_path else None,
        )

    except ValueError as e:
        logger.warning(f"요약 요청 오류: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.error(f"요약 처리 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"요약 처리 중 오류가 발생했습니다: {str(e)}",
        ) from e


# ============================================================================
# Streaming API Endpoint (SSE)
# ============================================================================


class StreamEvent(BaseModel):
    """SSE 스트림 이벤트"""

    type: str = Field(
        ...,
        description="이벤트 타입: thinking, content, done, error",
    )
    data: str = Field(
        ...,
        description="이벤트 데이터 (JSON 문자열)",
    )


async def _generate_sse_events(
    request: SummarizeRequest,
) -> AsyncGenerator[str, None]:
    """
    SSE 이벤트를 생성합니다.

    이벤트 형식:
    - thinking: AI의 추론 과정
    - content: 요약 텍스트
    - done: 완료 및 최종 결과 JSON
    - error: 에러 발생
    """
    start_time = time.time()

    # user_id 및 article_id 결정
    user_id = request.user_id or DEFAULT_USER_ID
    article_id = request.article_id or _generate_article_id(
        request.url, request.content
    )

    full_thinking = ""
    full_content = ""

    try:
        service = get_summary_service()

        async for event_type, text in service.summarize_stream(
            content=request.content,
            original_content=request.original_content,
        ):
            # 이벤트 데이터 구성
            event_data = json.dumps({"text": text}, ensure_ascii=False)

            if event_type == "thinking":
                full_thinking += text
                yield f"event: thinking\ndata: {event_data}\n\n"
            elif event_type == "content":
                full_content += text
                yield f"event: content\ndata: {event_data}\n\n"

        # 스트리밍 완료 후 결과 파싱
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Plain Text를 SummaryResult로 파싱
        result = SummaryService.parse_stream_result(full_content)

        # 결과 저장
        result_dict = {
            "bullet_points": result.bullet_points,
            "main_topic": result.main_topic,
            "model": service.model_name,
            "processing_time_ms": processing_time_ms,
            "thinking": full_thinking if full_thinking else None,
        }
        saved_path = await _save_summary_result(
            article_id=article_id,
            result=result_dict,
            user_id=user_id,
            url=request.url,
        )

        # 최종 결과 이벤트
        done_data = json.dumps(
            {
                "bullet_points": result.bullet_points,
                "main_topic": result.main_topic,
                "model": service.model_name,
                "processing_time_ms": processing_time_ms,
                "article_id": article_id,
                "saved_path": str(saved_path) if saved_path else None,
            },
            ensure_ascii=False,
        )

        yield f"event: done\ndata: {done_data}\n\n"

        logger.info(
            f"스트리밍 요약 API 완료: {len(result.bullet_points)}개 포인트, "
            f"처리시간={processing_time_ms}ms, article_id={article_id}"
        )

    except ValueError as e:
        error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"
        logger.warning(f"스트리밍 요약 요청 오류: {e}")

    except Exception as e:
        error_data = json.dumps(
            {"error": f"요약 처리 중 오류가 발생했습니다: {str(e)}"}, ensure_ascii=False
        )
        yield f"event: error\ndata: {error_data}\n\n"
        logger.error(f"스트리밍 요약 처리 실패: {e}")


@router.post("/stream")
async def summarize_stream(request: SummarizeRequest) -> StreamingResponse:
    """
    SSE 스트리밍으로 콘텐츠를 요약합니다.

    ## 이벤트 타입
    - **thinking**: AI의 추론 과정 텍스트
    - **content**: 요약 텍스트 청크
    - **done**: 최종 완료 결과 (SummarizeResponse와 동일한 구조)
    - **error**: 에러 발생

    ## 이벤트 형식 (SSE)
    ```
    event: thinking
    data: {"text": "글의 핵심을 분석하고 있습니다..."}

    event: content
    data: {"text": "[주제]\\nAI 시대의 변화..."}

    event: done
    data: {"bullet_points": [...], "main_topic": "...", "model": "...", ...}
    ```

    Returns:
        StreamingResponse with text/event-stream content type
    """
    return StreamingResponse(
        _generate_sse_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
        },
    )
