"""
Crawler Error Definitions

크롤링 관련 커스텀 에러 타입 및 사용자 친화적 메시지 시스템을 정의합니다.

에러 타입별 HTTP 상태 코드:
- 400: 잘못된 URL 형식, 빈 입력
- 415: 지원 불가 콘텐츠 (YouTube, Twitter 등)
- 422: 콘텐츠 없음 (빈 페이지)
- 502: 크롤링 실패 (네트워크 오류)
- 504: 타임아웃
"""

from enum import Enum
from typing import Optional


class CrawlErrorCode(str, Enum):
    """크롤링 에러 코드"""
    
    INVALID_URL_FORMAT = "INVALID_URL_FORMAT"
    EMPTY_INPUT = "EMPTY_INPUT"
    UNSUPPORTED_CONTENT = "UNSUPPORTED_CONTENT"
    NO_CONTENT = "NO_CONTENT"
    CRAWL_FAILED = "CRAWL_FAILED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"


# 에러 코드별 사용자 친화적 메시지 (한국어)
ERROR_MESSAGES: dict[CrawlErrorCode, str] = {
    CrawlErrorCode.INVALID_URL_FORMAT: "앗, 올바른 주소인지 확인해 주세요. URL 형식이 필요해요.",
    CrawlErrorCode.EMPTY_INPUT: "앗, 주소를 입력하지 않으셨어요. 분석할 URL을 넣어주세요.",
    CrawlErrorCode.UNSUPPORTED_CONTENT: "앗, 이 페이지의 내용은 읽어오기 어려워요. 일반적인 뉴스나 블로그 주소인가요?",
    CrawlErrorCode.NO_CONTENT: "앗, 페이지가 비어 있는 것 같아요. 다른 주소로 다시 시도해 볼까요?",
    CrawlErrorCode.CRAWL_FAILED: "앗, 페이지 내용을 불러오지 못했어요. 다른 주소로 시도해 주세요.",
    CrawlErrorCode.TIMEOUT: "앗, 응답 시간이 너무 길어지고 있어요. 잠시 후 다시 시도해 주시겠어요?",
    CrawlErrorCode.NETWORK_ERROR: "앗, 네트워크 연결에 문제가 있어요. 인터넷 연결을 확인해 주세요.",
}

# 에러 코드별 HTTP 상태 코드 매핑
ERROR_HTTP_STATUS: dict[CrawlErrorCode, int] = {
    CrawlErrorCode.INVALID_URL_FORMAT: 400,
    CrawlErrorCode.EMPTY_INPUT: 400,
    CrawlErrorCode.UNSUPPORTED_CONTENT: 415,
    CrawlErrorCode.NO_CONTENT: 422,
    CrawlErrorCode.CRAWL_FAILED: 502,
    CrawlErrorCode.TIMEOUT: 504,
    CrawlErrorCode.NETWORK_ERROR: 502,
}


class CrawlError(Exception):
    """
    크롤링 에러 기본 클래스
    
    Attributes:
        code: 에러 코드 (CrawlErrorCode)
        message: 사용자에게 표시할 메시지
        detail: 개발자용 상세 정보 (선택)
        http_status: HTTP 상태 코드
    """
    
    def __init__(
        self,
        code: CrawlErrorCode,
        message: Optional[str] = None,
        detail: Optional[str] = None,
    ):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "알 수 없는 오류가 발생했습니다.")
        self.detail = detail
        self.http_status = ERROR_HTTP_STATUS.get(code, 500)
        
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """API 응답용 딕셔너리 변환"""
        result = {
            "error_code": self.code.value,
            "message": self.message,
        }
        if self.detail:
            result["detail"] = self.detail
        return result


class InvalidURLError(CrawlError):
    """잘못된 URL 형식 에러"""
    
    def __init__(self, url: str, detail: Optional[str] = None):
        super().__init__(
            code=CrawlErrorCode.INVALID_URL_FORMAT,
            detail=detail or f"유효하지 않은 URL: {url}",
        )
        self.url = url


class EmptyInputError(CrawlError):
    """빈 입력 에러"""
    
    def __init__(self):
        super().__init__(code=CrawlErrorCode.EMPTY_INPUT)


class UnsupportedContentError(CrawlError):
    """지원하지 않는 콘텐츠 타입 에러"""
    
    def __init__(self, url: str, domain: str, reason: Optional[str] = None):
        super().__init__(
            code=CrawlErrorCode.UNSUPPORTED_CONTENT,
            detail=reason or f"지원하지 않는 콘텐츠 타입: {domain}",
        )
        self.url = url
        self.domain = domain


class NoContentError(CrawlError):
    """콘텐츠 없음 에러"""
    
    def __init__(self, url: str):
        super().__init__(
            code=CrawlErrorCode.NO_CONTENT,
            detail=f"콘텐츠를 추출할 수 없음: {url}",
        )
        self.url = url


class CrawlFailedError(CrawlError):
    """크롤링 실패 에러"""
    
    def __init__(self, url: str, reason: Optional[str] = None):
        super().__init__(
            code=CrawlErrorCode.CRAWL_FAILED,
            detail=reason or f"크롤링 실패: {url}",
        )
        self.url = url


class CrawlTimeoutError(CrawlError):
    """타임아웃 에러"""
    
    def __init__(self, url: str, timeout_seconds: float):
        super().__init__(
            code=CrawlErrorCode.TIMEOUT,
            detail=f"타임아웃 ({timeout_seconds}초 초과): {url}",
        )
        self.url = url
        self.timeout_seconds = timeout_seconds


class NetworkError(CrawlError):
    """네트워크 에러"""
    
    def __init__(self, url: str, reason: Optional[str] = None):
        super().__init__(
            code=CrawlErrorCode.NETWORK_ERROR,
            detail=reason or f"네트워크 오류: {url}",
        )
        self.url = url

