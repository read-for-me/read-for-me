"""
Crawl API Endpoints

URL을 받아 크롤링 후 정제된 아티클을 반환하는 API 엔드포인트입니다.

Endpoints:
- POST /api/v1/crawl: URL 크롤링
- GET /api/v1/crawl/supported-domains: 지원 도메인 목록
- GET /api/v1/crawl/check-support: URL 지원 여부 확인

에러 코드:
- INVALID_URL_FORMAT (400): 잘못된 URL 형식
- EMPTY_INPUT (400): 빈 입력
- UNSUPPORTED_CONTENT (415): 지원 불가 콘텐츠 (YouTube, Twitter 등)
- NO_CONTENT (422): 콘텐츠 없음 (빈 페이지)
- CRAWL_FAILED (502): 크롤링 실패 (네트워크 오류)
- TIMEOUT (504): 타임아웃
"""

import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field, HttpUrl

from app.services.crawlers import (
    CleanedArticle,
    CrawlerFactory,
    CrawlError,
    CrawlErrorCode,
    CrawlFailedError,
    CrawlTimeoutError,
    NetworkError,
    NoContentError,
    UnsupportedContentError,
    UnsupportedURLError,
)
from app.services.storage import get_storage_service

router = APIRouter(prefix="/crawl", tags=["crawl"])

# 기본 사용자 ID (프로토타입용)
DEFAULT_USER_ID = "default"


# ============================================================================
# Request Schemas
# ============================================================================


class CrawlRequest(BaseModel):
    """크롤링 요청 스키마"""

    url: HttpUrl = Field(
        ...,
        description="크롤링할 URL",
    )
    user_id: str | None = Field(
        None,
        description="사용자 ID (선택). 없으면 기본값 'default' 사용",
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _extract_article_id(url: str, platform: str) -> str:
    """URL에서 아티클 ID/슬러그 추출"""
    parsed = urlparse(url)

    if platform == "geeknews":
        # GeekNews: topic?id=XXXXX에서 ID 추출
        query_params = parse_qs(parsed.query)
        topic_id = query_params.get("id", [None])[0]
        if topic_id:
            return f"topic_{topic_id}"

    elif platform == "medium":
        # Medium: URL 경로의 마지막 부분 (슬러그) 추출
        path_parts = parsed.path.strip("/").split("/")
        if path_parts:
            slug = path_parts[-1]
            # 슬러그에서 해시 부분 제거 (예: article-title-abc123def456)
            # 마지막 12자리 해시를 제거
            slug_clean = re.sub(r"-[a-f0-9]{10,}$", "", slug)
            if slug_clean:
                return slug_clean[:50]  # 최대 50자

    # 기본값: URL 해시
    return f"article_{abs(hash(url)) % 100000000}"


async def save_crawl_result(
    cleaned: CleanedArticle,
    user_id: str = DEFAULT_USER_ID,
) -> str | None:
    """
    크롤링 결과를 저장합니다 (StorageService 사용).

    저장 경로: users/{user_id}/crawled/{article_id}_{timestamp}.json

    Args:
        cleaned: 정제된 아티클 데이터
        user_id: 사용자 ID

    Returns:
        저장된 경로 (실패 시 None)
    """
    try:
        storage = get_storage_service()

        # 파일명 생성
        article_id = _extract_article_id(cleaned.url, cleaned.platform)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"{article_id}_{timestamp}.json"

        # 저장 경로
        path = f"users/{user_id}/crawled/{filename}"

        # JSON 저장
        data = {
            "user_id": user_id,
            **cleaned.model_dump(),
        }
        saved_path = await storage.save_json(path, data)

        logger.info(f"크롤링 결과 저장됨: {saved_path}")
        return saved_path

    except Exception as e:
        logger.error(f"크롤링 결과 저장 실패: {e}")
        return None


class CrawlErrorResponse(BaseModel):
    """크롤링 에러 응답 스키마"""

    error_code: str = Field(..., description="에러 코드")
    message: str = Field(..., description="사용자 친화적 에러 메시지")
    detail: str | None = Field(None, description="개발자용 상세 정보")


def raise_crawl_error(error: CrawlError) -> None:
    """CrawlError를 HTTPException으로 변환하여 raise"""
    raise HTTPException(
        status_code=error.http_status,
        detail=error.to_dict(),
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "",
    response_model=CleanedArticle,
    summary="URL 크롤링",
    responses={
        400: {
            "model": CrawlErrorResponse,
            "description": "잘못된 URL 형식 또는 빈 입력",
        },
        415: {"model": CrawlErrorResponse, "description": "지원 불가 콘텐츠"},
        422: {"model": CrawlErrorResponse, "description": "콘텐츠 없음"},
        502: {"model": CrawlErrorResponse, "description": "크롤링 실패"},
        504: {"model": CrawlErrorResponse, "description": "타임아웃"},
    },
)
async def crawl_url(request: CrawlRequest) -> CleanedArticle:
    """
    URL을 받아 크롤링 후 정제된 아티클을 반환합니다.

    ## 처리 흐름
    1. CrawlerFactory로 적절한 크롤러 선택
    2. crawler.extract()로 콘텐츠 추출
    3. CleanedArticle.from_crawled()로 변환 후 반환

    ## 지원 플랫폼
    - GeekNews: `https://news.hada.io/topic?id=XXXXX`
    - Medium: `https://medium.com/@username/...`
    - 일반 웹사이트: trafilatura 기반 범용 크롤러

    ## 저장 경로
    - `data/users/{user_id}/crawled/{article_id}_{timestamp}.json`

    ## 에러 코드
    - INVALID_URL_FORMAT (400): 잘못된 URL 형식
    - EMPTY_INPUT (400): 빈 입력
    - UNSUPPORTED_CONTENT (415): 지원 불가 콘텐츠 (YouTube, Twitter 등)
    - NO_CONTENT (422): 콘텐츠 없음 (빈 페이지)
    - CRAWL_FAILED (502): 크롤링 실패
    - TIMEOUT (504): 타임아웃

    Args:
        request: 크롤링 요청 (url, user_id 필드 포함)

    Returns:
        CleanedArticle: 정제된 아티클 데이터

    Raises:
        HTTPException: 크롤링 실패 시
    """
    url = str(request.url)
    user_id = request.user_id or DEFAULT_USER_ID
    logger.info(f"크롤링 요청 수신: {url} (user_id={user_id})")

    # 1. 크롤러 선택
    try:
        crawler = CrawlerFactory.get_crawler(url)
        logger.debug(f"크롤러 선택됨: {crawler.platform_name}")
    except UnsupportedURLError as e:
        logger.warning(f"지원하지 않는 URL: {e.domain}")
        raise_crawl_error(
            UnsupportedContentError(
                url=url,
                domain=e.domain,
                reason=e.reason,
            )
        )

    # 2. 크롤링 실행
    try:
        crawled = await crawler.extract(url)
    except httpx.TimeoutException:
        logger.error(f"크롤링 타임아웃: {url}")
        raise_crawl_error(CrawlTimeoutError(url=url, timeout_seconds=30.0))
    except httpx.RequestError as e:
        logger.error(f"네트워크 오류: {e}")
        raise_crawl_error(NetworkError(url=url, reason=str(e)))
    except Exception as e:
        logger.error(f"크롤링 중 예외 발생: {e}")
        raise_crawl_error(CrawlFailedError(url=url, reason=str(e)))

    # 3. 결과 검증
    if crawled is None:
        logger.error(f"크롤링 결과 없음: {url}")
        raise_crawl_error(CrawlFailedError(url=url, reason="크롤링 결과가 없습니다"))

    # 4. 콘텐츠 검증 (빈 콘텐츠 체크)
    if not crawled.content or len(crawled.content.strip()) < 50:
        logger.warning(f"콘텐츠가 너무 짧음: {url} ({len(crawled.content)} chars)")
        raise_crawl_error(NoContentError(url=url))

    # 5. 정제
    cleaned = CleanedArticle.from_crawled(crawled)
    logger.info(f"크롤링 완료: {cleaned.title}")

    # 6. 결과 저장 (비동기, 실패해도 응답은 반환)
    await save_crawl_result(cleaned, user_id)

    return cleaned


@router.get(
    "/supported-domains",
    response_model=list[str],
    summary="지원 도메인 목록",
)
async def get_supported_domains() -> list[str]:
    """
    지원하는 도메인 목록을 반환합니다.

    Returns:
        list[str]: 지원하는 도메인 패턴 목록

    Example:
        ```json
        ["news.hada.io", "medium.com"]
        ```
    """
    domains = CrawlerFactory.get_supported_domains()
    logger.debug(f"지원 도메인 조회: {domains}")
    return domains


class UrlSupportResponse(BaseModel):
    """URL 지원 여부 응답 스키마"""

    url: str = Field(..., description="확인한 URL")
    is_supported: bool = Field(..., description="지원 여부")
    platform: str | None = Field(
        None, description="플랫폼 이름 (geeknews, medium, generic)"
    )
    is_specialized: bool = Field(False, description="전용 크롤러 사용 여부")
    domain: str = Field("", description="파싱된 도메인")
    error_code: str | None = Field(None, description="지원하지 않는 경우 에러 코드")
    error_message: str | None = Field(
        None, description="지원하지 않는 경우 에러 메시지"
    )


@router.get(
    "/check-support",
    response_model=UrlSupportResponse,
    summary="URL 지원 여부 확인",
)
async def check_url_support(
    url: str = Query(..., description="확인할 URL"),
) -> UrlSupportResponse:
    """
    URL이 지원되는지 확인합니다.

    플랫폼 감지 결과:
    - geeknews: GeekNews 전용 크롤러
    - medium: Medium 전용 크롤러
    - generic: trafilatura 기반 범용 크롤러
    - unsupported: 지원하지 않는 URL (YouTube, Twitter 등)

    Args:
        url: 확인할 URL (쿼리 파라미터)

    Returns:
        UrlSupportResponse: 지원 여부 및 플랫폼 정보

    Example:
        ```
        GET /api/v1/crawl/check-support?url=https://news.hada.io/topic?id=24268

        Response:
        {
            "url": "https://news.hada.io/topic?id=24268",
            "is_supported": true,
            "platform": "geeknews",
            "is_specialized": true,
            "domain": "news.hada.io",
            "error_code": null,
            "error_message": null
        }
        ```
    """
    # 빈 입력 체크
    if not url or not url.strip():
        return UrlSupportResponse(
            url=url,
            is_supported=False,
            platform=None,
            is_specialized=False,
            domain="",
            error_code=CrawlErrorCode.EMPTY_INPUT.value,
            error_message="앗, 주소를 입력하지 않으셨어요. 분석할 URL을 넣어주세요.",
        )

    # 기본 URL 형식 체크
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return UrlSupportResponse(
            url=url,
            is_supported=False,
            platform=None,
            is_specialized=False,
            domain="",
            error_code=CrawlErrorCode.INVALID_URL_FORMAT.value,
            error_message="앗, 올바른 주소인지 확인해 주세요. URL 형식이 필요해요.",
        )

    # 플랫폼 감지
    result = CrawlerFactory.detect_platform(url)

    if result["platform"] == "unsupported":
        return UrlSupportResponse(
            url=url,
            is_supported=False,
            platform=None,
            is_specialized=False,
            domain=result["domain"],
            error_code=CrawlErrorCode.UNSUPPORTED_CONTENT.value,
            error_message="앗, 이 페이지의 내용은 읽어오기 어려워요. 일반적인 뉴스나 블로그 주소인가요?",
        )

    return UrlSupportResponse(
        url=url,
        is_supported=True,
        platform=result["platform"],
        is_specialized=result["is_specialized"],
        domain=result["domain"],
        error_code=None,
        error_message=None,
    )
