"""
Crawlers Package

크롤링 관련 모듈을 제공합니다.

공개 API:
- schemas: 데이터 모델 (CrawlRequest, CrawledArticle, CleanedArticle, ArticleMetadata)
- base: 추상 기본 클래스 (BaseCrawler, BaseTextExtractor)
- geeknews: GeekNews 크롤러 (GeekNewsCrawler)
- medium: Medium 크롤러 (MediumCrawler)
- generic: 범용 크롤러 (GenericCrawler) - trafilatura 기반
- factory: 크롤러 팩토리 (CrawlerFactory, UnsupportedURLError)
- errors: 에러 타입 및 메시지 시스템
"""

from app.services.crawlers.base import (
    BaseCrawler,
    BaseTextExtractor,
)
from app.services.crawlers.errors import (
    ERROR_HTTP_STATUS,
    ERROR_MESSAGES,
    CrawlError,
    CrawlErrorCode,
    CrawlFailedError,
    CrawlTimeoutError,
    EmptyInputError,
    InvalidURLError,
    NetworkError,
    NoContentError,
    UnsupportedContentError,
)
from app.services.crawlers.factory import (
    CrawlerFactory,
    UnsupportedURLError,
)
from app.services.crawlers.geeknews import GeekNewsCrawler
from app.services.crawlers.generic import GenericCrawler
from app.services.crawlers.medium import MediumCrawler
from app.services.crawlers.schemas import (
    ArticleMetadata,
    CleanedArticle,
    CrawledArticle,
    CrawlRequest,
)

__all__ = [
    # Schemas
    "CrawlRequest",
    "ArticleMetadata",
    "CrawledArticle",
    "CleanedArticle",
    # Base classes
    "BaseCrawler",
    "BaseTextExtractor",
    # Crawlers
    "GeekNewsCrawler",
    "MediumCrawler",
    "GenericCrawler",
    # Factory
    "CrawlerFactory",
    "UnsupportedURLError",
    # Errors
    "CrawlError",
    "CrawlErrorCode",
    "InvalidURLError",
    "EmptyInputError",
    "UnsupportedContentError",
    "NoContentError",
    "CrawlFailedError",
    "CrawlTimeoutError",
    "NetworkError",
    "ERROR_MESSAGES",
    "ERROR_HTTP_STATUS",
]
