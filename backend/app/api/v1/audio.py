"""
Audio API Endpoint

뉴스 스크립트 생성 및 TTS 음성 합성 API를 제공합니다.
Step 1: 콘텐츠 → 3분 분량의 뉴스 스크립트 생성
Step 2: TTS 음성 합성 (OpenAI gpt-4o-mini-tts)
"""

import hashlib
import json
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.audio import AudioService, get_audio_service
from app.services.storage import get_storage_service, is_gcs_storage, GCSStorageService
from output_schemas.audio import NewsScript


router = APIRouter(prefix="/audio", tags=["audio"])

# 기본 사용자 ID (프로토타입용)
DEFAULT_USER_ID = "default"


# ============================================================================
# Request/Response Schemas
# ============================================================================


class GenerateScriptRequest(BaseModel):
    """스크립트 생성 요청 스키마"""

    content: str = Field(
        ...,
        min_length=10,
        description="스크립트로 변환할 콘텐츠 텍스트",
    )
    original_content: Optional[str] = Field(
        None,
        description="원본 외부 링크 콘텐츠 (GeekNews 등). 있으면 content와 병합하여 스크립트 생성",
    )
    url: Optional[str] = Field(
        None,
        description="원본 URL (캐싱용, 선택)",
    )
    article_id: Optional[str] = Field(
        None,
        description="아티클 ID (저장용, 선택). 없으면 URL 또는 content 해시 기반 자동 생성",
    )
    user_id: Optional[str] = Field(
        None,
        description="사용자 ID (선택). 없으면 기본값 'default' 사용",
    )


class GenerateScriptResponse(BaseModel):
    """스크립트 생성 응답 스키마"""

    user_id: str = Field(
        ...,
        description="사용자 ID",
    )
    article_id: str = Field(
        ...,
        description="아티클 ID",
    )
    script: NewsScript = Field(
        ...,
        description="생성된 뉴스 스크립트 (paragraphs, title, estimated_duration_sec, total_characters)",
    )
    model: str = Field(
        ...,
        description="사용된 모델 이름",
    )
    processing_time_ms: int = Field(
        ...,
        description="처리 시간 (밀리초)",
    )
    saved_path: Optional[str] = Field(
        None,
        description="저장된 파일 경로 (저장 실패 시 None)",
    )


class SynthesizeRequest(BaseModel):
    """TTS 합성 요청 스키마"""

    article_id: str = Field(
        ...,
        description="합성할 스크립트의 아티클 ID",
    )
    user_id: Optional[str] = Field(
        None,
        description="사용자 ID (선택). 없으면 기본값 'default' 사용",
    )


class SynthesizeResponse(BaseModel):
    """TTS 합성 응답 스키마"""

    audio_url: str = Field(
        ...,
        description="생성된 오디오 파일 URL (/api/v1/audio/{article_id}.mp3)",
    )
    duration_seconds: float = Field(
        ...,
        description="오디오 길이 (초)",
    )
    file_size_bytes: int = Field(
        ...,
        description="파일 크기 (바이트)",
    )
    user_id: str = Field(
        ...,
        description="사용자 ID",
    )
    article_id: str = Field(
        ...,
        description="아티클 ID",
    )
    processing_time_ms: int = Field(
        ...,
        description="처리 시간 (밀리초)",
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _generate_article_id(url: Optional[str], content: str) -> str:
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
    return f"script_{hash_value}"


async def _save_script_result(
    article_id: str,
    result: dict,
    user_id: str = DEFAULT_USER_ID,
    url: Optional[str] = None,
) -> Optional[str]:
    """
    스크립트 결과를 저장합니다 (StorageService 사용).
    
    저장 경로: users/{user_id}/audio/{article_id}_{timestamp}.json
    
    Args:
        article_id: 아티클 ID
        result: 스크립트 결과 딕셔너리
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
        path = f"users/{user_id}/audio/{filename}"
        
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
        
        logger.info(f"스크립트 결과 저장됨: {saved_path}")
        return saved_path
        
    except Exception as e:
        logger.error(f"스크립트 결과 저장 실패: {e}")
        return None


async def _find_latest_script_json(user_id: str, article_id: str) -> Optional[dict]:
    """
    가장 최근에 저장된 스크립트 JSON 파일을 찾아 로드합니다 (StorageService 사용).
    
    Args:
        user_id: 사용자 ID
        article_id: 아티클 ID
        
    Returns:
        스크립트 데이터 딕셔너리 (없으면 None)
    """
    storage = get_storage_service()
    prefix = f"users/{user_id}/audio/"
    pattern = f"{article_id}_*.json"
    
    # 파일 목록 조회
    files = await storage.list_files(prefix, pattern)
    
    if not files:
        return None
    
    # 가장 최근 파일 선택 (파일명 기준 정렬 - timestamp가 포함되어 있음)
    latest_file = sorted(files)[-1]
    
    # JSON 로드
    return await storage.load_json(latest_file)


def _get_audio_storage_path(user_id: str, article_id: str) -> str:
    """
    오디오 파일의 스토리지 경로를 반환합니다.
    
    Args:
        user_id: 사용자 ID
        article_id: 아티클 ID
        
    Returns:
        스토리지 경로 (예: users/default/audio/script_xxx.mp3)
    """
    return f"users/{user_id}/audio/{article_id}.mp3"


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/script", response_model=GenerateScriptResponse)
async def generate_script(request: GenerateScriptRequest) -> GenerateScriptResponse:
    """
    콘텐츠를 뉴스 스크립트로 변환합니다.

    - **content**: 변환할 텍스트 콘텐츠 (최소 10자)
    - **original_content**: 원본 외부 링크 콘텐츠 (선택). 있으면 content와 병합
    - **url**: 원본 URL (선택, 캐싱용)
    - **article_id**: 아티클 ID (선택, 저장용). 없으면 자동 생성
    - **user_id**: 사용자 ID (선택). 없으면 기본값 'default' 사용

    ## 출력 스크립트 특징
    - **분량**: 3분 (약 900~1,050자)
    - **문단 수**: 8~12개 (TTS 청킹 최적화)
    - **톤**: 남성 뉴스 아나운서 스타일

    ## 저장 경로
    - `data/users/{user_id}/audio/{article_id}_{timestamp}.json`

    Returns:
        GenerateScriptResponse: 생성된 뉴스 스크립트 결과
    """
    start_time = time.time()

    # user_id 및 article_id 결정
    user_id = request.user_id or DEFAULT_USER_ID
    article_id = request.article_id or _generate_article_id(request.url, request.content)

    try:
        service = get_audio_service()
        script = await service.generate_script(
            content=request.content,
            original_content=request.original_content,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # 스크립트 결과 저장
        result_dict = {
            "script": script.model_dump(),
            "model": service.model_name,
            "processing_time_ms": processing_time_ms,
        }
        saved_path = await _save_script_result(
            article_id=article_id,
            result=result_dict,
            user_id=user_id,
            url=request.url,
        )

        logger.info(
            f"스크립트 API 완료: {len(script.paragraphs)}개 문단, "
            f"총 {script.total_characters}자, "
            f"처리시간={processing_time_ms}ms, article_id={article_id}, user_id={user_id}"
        )

        return GenerateScriptResponse(
            user_id=user_id,
            article_id=article_id,
            script=script,
            model=service.model_name,
            processing_time_ms=processing_time_ms,
            saved_path=str(saved_path) if saved_path else None,
        )

    except ValueError as e:
        logger.warning(f"스크립트 요청 오류: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"스크립트 처리 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"스크립트 처리 중 오류가 발생했습니다: {str(e)}",
        )


# ============================================================================
# Streaming API Endpoint (SSE)
# ============================================================================


async def _generate_script_sse_events(
    request: GenerateScriptRequest,
) -> AsyncGenerator[str, None]:
    """
    SSE 이벤트를 생성합니다.
    
    이벤트 형식:
    - thinking: AI의 추론 과정
    - content: 스크립트 텍스트
    - done: 완료 및 최종 결과 JSON
    - error: 에러 발생
    """
    start_time = time.time()
    
    # user_id 및 article_id 결정
    user_id = request.user_id or DEFAULT_USER_ID
    article_id = request.article_id or _generate_article_id(request.url, request.content)
    
    full_thinking = ""
    full_content = ""
    
    try:
        service = get_audio_service()
        
        async for event_type, text in service.generate_script_stream(
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
        
        # Plain Text를 NewsScript로 파싱
        result = AudioService.parse_stream_result(full_content)
        
        # 결과 저장
        result_dict = {
            "script": result.model_dump(),
            "model": service.model_name,
            "processing_time_ms": processing_time_ms,
            "thinking": full_thinking if full_thinking else None,
        }
        saved_path = await _save_script_result(
            article_id=article_id,
            result=result_dict,
            user_id=user_id,
            url=request.url,
        )
        
        # 최종 결과 이벤트
        done_data = json.dumps({
            "user_id": user_id,
            "article_id": article_id,
            "script": result.model_dump(),
            "model": service.model_name,
            "processing_time_ms": processing_time_ms,
            "saved_path": str(saved_path) if saved_path else None,
        }, ensure_ascii=False)
        
        yield f"event: done\ndata: {done_data}\n\n"
        
        logger.info(
            f"스트리밍 스크립트 API 완료: {len(result.paragraphs)}개 문단, "
            f"처리시간={processing_time_ms}ms, article_id={article_id}"
        )
        
    except ValueError as e:
        error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"
        logger.warning(f"스트리밍 스크립트 요청 오류: {e}")
        
    except Exception as e:
        error_data = json.dumps({"error": f"스크립트 처리 중 오류가 발생했습니다: {str(e)}"}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"
        logger.error(f"스트리밍 스크립트 처리 실패: {e}")


@router.post("/script/stream")
async def generate_script_stream(request: GenerateScriptRequest) -> StreamingResponse:
    """
    SSE 스트리밍으로 뉴스 스크립트를 생성합니다.

    ## 이벤트 타입
    - **thinking**: AI의 추론 과정 텍스트
    - **content**: 스크립트 텍스트 청크
    - **done**: 최종 완료 결과 (GenerateScriptResponse와 동일한 구조)
    - **error**: 에러 발생

    ## 이벤트 형식 (SSE)
    ```
    event: thinking
    data: {"text": "뉴스 대본 구조를 분석하고 있습니다..."}

    event: content
    data: {"text": "[제목]\\nAI가 바꾸는 미래..."}

    event: done
    data: {"user_id": "default", "article_id": "...", "script": {...}, ...}
    ```

    Returns:
        StreamingResponse with text/event-stream content type
    """
    return StreamingResponse(
        _generate_script_sse_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
        },
    )


# ============================================================================
# TTS 음성 합성 API Endpoints
# ============================================================================


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_audio(request: SynthesizeRequest) -> SynthesizeResponse:
    """
    저장된 스크립트를 기반으로 TTS 음성을 합성합니다.

    - **article_id**: 합성할 스크립트의 아티클 ID (필수)
    - **user_id**: 사용자 ID (선택). 없으면 기본값 'default' 사용

    ## 처리 과정
    1. 저장된 스크립트 JSON 파일 로드
    2. 각 문단을 OpenAI TTS API로 음성 합성 (병렬 처리)
    3. 문단 사이에 silence padding 추가
    4. 전체 오디오 병합 후 MP3 저장

    ## 저장 경로
    - `users/{user_id}/audio/{article_id}.mp3`

    Returns:
        SynthesizeResponse: 생성된 오디오 파일 정보
    """
    start_time = time.time()

    user_id = request.user_id or DEFAULT_USER_ID
    article_id = request.article_id

    # 저장된 스크립트 JSON 찾기
    script_data = await _find_latest_script_json(user_id, article_id)

    if not script_data:
        raise HTTPException(
            status_code=404,
            detail=f"스크립트를 찾을 수 없습니다: article_id={article_id}, user_id={user_id}",
        )

    # 스크립트 파싱
    script_dict = script_data.get("script")
    if not script_dict:
        raise HTTPException(
            status_code=400,
            detail="스크립트 데이터가 올바르지 않습니다.",
        )

    try:
        script = NewsScript(**script_dict)
    except Exception as e:
        logger.error(f"스크립트 파싱 실패: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"스크립트 파싱 실패: {str(e)}",
        )

    try:
        service = get_audio_service()
        result = await service.synthesize_speech(
            script=script,
            article_id=article_id,
            user_id=user_id,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # 오디오 URL 생성
        audio_url = f"/api/v1/audio/{article_id}.mp3?user_id={user_id}"

        logger.info(
            f"TTS 합성 API 완료: article_id={article_id}, "
            f"duration={result['duration_sec']:.1f}초, "
            f"size={result['file_size_bytes'] / 1024:.1f}KB, "
            f"처리시간={processing_time_ms}ms"
        )

        return SynthesizeResponse(
            audio_url=audio_url,
            duration_seconds=result["duration_sec"],
            file_size_bytes=result["file_size_bytes"],
            user_id=user_id,
            article_id=article_id,
            processing_time_ms=processing_time_ms,
        )

    except ValueError as e:
        logger.warning(f"TTS 합성 요청 오류: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"TTS 합성 처리 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"TTS 합성 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/{article_id}.mp3")
async def get_audio_file(
    article_id: str,
    user_id: str = Query(default=DEFAULT_USER_ID, description="사용자 ID"),
):
    """
    생성된 오디오 파일을 스트리밍합니다.

    - **article_id**: 아티클 ID (path parameter)
    - **user_id**: 사용자 ID (query parameter, 기본값: 'default')

    Returns:
        - Local Storage: FileResponse (MP3 오디오 파일)
        - GCS Storage: RedirectResponse (Signed URL로 302 리다이렉트)
    """
    storage = get_storage_service()
    audio_path = _get_audio_storage_path(user_id, article_id)

    # 파일 존재 확인
    if not storage.exists(audio_path):
        raise HTTPException(
            status_code=404,
            detail=f"오디오 파일을 찾을 수 없습니다: article_id={article_id}, user_id={user_id}",
        )

    # GCS인 경우: Signed URL로 리다이렉트
    if isinstance(storage, GCSStorageService):
        signed_url = await storage.get_download_url(
            audio_path,
            expiry_minutes=settings.GCS_SIGNED_URL_EXPIRY_MINUTES,
        )
        return RedirectResponse(url=signed_url, status_code=302)

    # Local인 경우: FileResponse로 직접 서빙
    local_path = storage.get_local_path(audio_path)
    if local_path is None or not local_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"오디오 파일을 찾을 수 없습니다: article_id={article_id}, user_id={user_id}",
        )

    return FileResponse(
        path=local_path,
        media_type="audio/mpeg",
        filename=f"{article_id}.mp3",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )
