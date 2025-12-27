"""
Crawler Factory Module

URL 도메인 기반으로 적절한 크롤러를 선택하는 팩토리 클래스를 제공합니다.
전용 크롤러가 없는 URL에 대해서는 GenericCrawler를 fallback으로 사용합니다.

Usage:
    from app.services.crawlers import CrawlerFactory

    # 크롤러 가져오기 (자동으로 적합한 크롤러 선택)
    crawler = CrawlerFactory.get_crawler("https://news.hada.io/topic?id=24268")
    article = await crawler.extract(url)

    # 플랫폼 감지 결과 확인
    result = CrawlerFactory.detect_platform("https://example.com/article")
    # result: {"platform": "generic", "is_specialized": False}

확장성:
    새 플랫폼 추가 시 _crawlers 딕셔너리에 한 줄만 추가하면 됩니다.
"""

from urllib.parse import urlparse

from loguru import logger

from app.services.crawlers.base import BaseCrawler
from app.services.crawlers.geeknews import GeekNewsCrawler
from app.services.crawlers.generic import GenericCrawler
from app.services.crawlers.medium import MediumCrawler


class UnsupportedURLError(ValueError):
    """
    지원하지 않는 URL에 대한 예외

    Note: GenericCrawler fallback이 활성화된 경우,
          이 예외는 GenericCrawler도 처리할 수 없는 URL에서만 발생합니다.
          (예: YouTube, Twitter 등 멀티미디어/소셜 플랫폼)
    """

    def __init__(self, url: str, domain: str, reason: str | None = None):
        self.url = url
        self.domain = domain
        self.reason = reason or "지원하지 않는 URL입니다"
        super().__init__(f"{self.reason}: {domain}")


class CrawlerFactory:
    """
    URL 도메인 기반 크롤러 선택 팩토리

    URL에서 도메인을 추출하고 적절한 크롤러를 반환합니다.
    전용 크롤러가 없는 URL에 대해서는 GenericCrawler를 fallback으로 사용합니다.

    지원 플랫폼:
    - GeekNews: news.hada.io (전용 크롤러)
    - Medium: medium.com, *.medium.com (전용 크롤러)
    - 기타 웹사이트: GenericCrawler (trafilatura 기반)

    Usage:
        # 크롤러 가져오기
        crawler = CrawlerFactory.get_crawler("https://news.hada.io/topic?id=24268")

        # 지원 도메인 확인
        domains = CrawlerFactory.get_supported_domains()

        # 플랫폼 감지
        result = CrawlerFactory.detect_platform("https://example.com/article")
    """

    # 도메인 → 전용 크롤러 클래스 매핑
    # 키는 도메인 패턴, 값은 크롤러 클래스
    _crawlers: dict[str, type[BaseCrawler]] = {
        "news.hada.io": GeekNewsCrawler,
        "medium.com": MediumCrawler,
    }

    @classmethod
    def get_crawler(cls, url: str, use_fallback: bool = True, **kwargs) -> BaseCrawler:
        """
        URL에서 도메인을 추출하고 적절한 크롤러를 반환합니다.

        전용 크롤러가 없는 URL에 대해서는 GenericCrawler를 fallback으로 사용합니다.

        Args:
            url: 크롤링할 URL
            use_fallback: GenericCrawler fallback 사용 여부 (기본값 True)
            **kwargs: 크롤러 생성자에 전달할 추가 인자
                - GeekNewsCrawler: include_comments (bool), crawl_original (bool)
                - GenericCrawler: target_language (str)
                - 공통: timeout (float), headers (dict)

        Returns:
            해당 URL에 적합한 BaseCrawler 인스턴스

        Raises:
            UnsupportedURLError: 지원하지 않는 URL인 경우 (fallback 비활성화 또는 GenericCrawler도 지원 불가)

        Example:
            >>> # 전용 크롤러 사용
            >>> crawler = CrawlerFactory.get_crawler(
            ...     "https://news.hada.io/topic?id=24268",
            ...     include_comments=True
            ... )

            >>> # GenericCrawler fallback 사용
            >>> crawler = CrawlerFactory.get_crawler(
            ...     "https://example.com/article"
            ... )
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # www. 접두사 제거
        if domain.startswith("www."):
            domain = domain[4:]

        logger.debug(f"URL 도메인 파싱: {url} → {domain}")

        # 1. 전용 크롤러 매칭 시도
        for pattern, crawler_cls in cls._crawlers.items():
            if cls._match_domain(domain, pattern):
                logger.info(
                    f"전용 크롤러 선택: {crawler_cls.platform_name} for {domain}"
                )
                return crawler_cls(**kwargs)

        # 2. fallback: GenericCrawler 사용
        if use_fallback:
            generic_crawler = GenericCrawler(**kwargs)

            # GenericCrawler가 해당 URL을 처리할 수 있는지 확인
            if generic_crawler.validate_url(url):
                logger.info(f"범용 크롤러 선택: generic for {domain}")
                return generic_crawler
            else:
                # GenericCrawler도 지원하지 않는 URL (예: YouTube, Twitter 등)
                logger.warning(f"지원하지 않는 콘텐츠 타입: {domain}")
                raise UnsupportedURLError(
                    url=url,
                    domain=domain,
                    reason="이 사이트의 콘텐츠는 텍스트 추출이 지원되지 않습니다",
                )

        # fallback 비활성화 시 기존 동작 유지
        logger.warning(f"지원하지 않는 도메인: {domain}")
        raise UnsupportedURLError(url=url, domain=domain)

    @classmethod
    def _match_domain(cls, domain: str, pattern: str) -> bool:
        """
        도메인이 패턴과 일치하는지 확인합니다.

        다음 케이스를 처리합니다:
        - 정확히 일치: news.hada.io == news.hada.io
        - 서브도메인 일치: towardsdatascience.medium.com → medium.com

        Args:
            domain: 검사할 도메인 (www. 제거됨)
            pattern: 매칭할 패턴

        Returns:
            일치하면 True, 아니면 False
        """
        # 정확히 일치
        if domain == pattern:
            return True

        # 서브도메인 일치 (예: *.medium.com)
        if domain.endswith(f".{pattern}"):
            return True

        return False

    @classmethod
    def get_supported_domains(cls) -> list[str]:
        """
        전용 크롤러가 있는 도메인 목록을 반환합니다.

        Note: GenericCrawler는 대부분의 웹사이트를 지원하므로,
              이 목록에 없는 도메인도 크롤링이 가능합니다.

        Returns:
            전용 크롤러가 있는 도메인 패턴 목록

        Example:
            >>> CrawlerFactory.get_supported_domains()
            ['news.hada.io', 'medium.com']
        """
        return list(cls._crawlers.keys())

    @classmethod
    def detect_platform(cls, url: str) -> dict:
        """
        URL에서 플랫폼을 감지합니다.

        전용 크롤러가 있는 플랫폼인지, GenericCrawler를 사용해야 하는지,
        또는 지원되지 않는 URL인지 판별합니다.

        Args:
            url: 확인할 URL

        Returns:
            플랫폼 감지 결과 딕셔너리:
            - platform: 플랫폼 이름 (geeknews, medium, generic, unsupported)
            - is_specialized: 전용 크롤러 사용 여부
            - domain: 파싱된 도메인

        Example:
            >>> CrawlerFactory.detect_platform("https://news.hada.io/topic?id=24268")
            {"platform": "geeknews", "is_specialized": True, "domain": "news.hada.io"}

            >>> CrawlerFactory.detect_platform("https://example.com/article")
            {"platform": "generic", "is_specialized": False, "domain": "example.com"}

            >>> CrawlerFactory.detect_platform("https://youtube.com/watch?v=xxx")
            {"platform": "unsupported", "is_specialized": False, "domain": "youtube.com"}
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            if domain.startswith("www."):
                domain = domain[4:]

            # 1. 전용 크롤러 확인
            for pattern, crawler_cls in cls._crawlers.items():
                if cls._match_domain(domain, pattern):
                    return {
                        "platform": crawler_cls.platform_name,
                        "is_specialized": True,
                        "domain": domain,
                    }

            # 2. GenericCrawler 지원 여부 확인
            generic_crawler = GenericCrawler()
            if generic_crawler.validate_url(url):
                return {
                    "platform": "generic",
                    "is_specialized": False,
                    "domain": domain,
                }

            # 3. 지원하지 않는 URL
            return {
                "platform": "unsupported",
                "is_specialized": False,
                "domain": domain,
            }

        except Exception:
            return {
                "platform": "unsupported",
                "is_specialized": False,
                "domain": "",
            }

    @classmethod
    def is_supported(cls, url: str, include_generic: bool = True) -> bool:
        """
        URL이 지원되는지 확인합니다.

        Args:
            url: 확인할 URL
            include_generic: GenericCrawler 지원 여부도 포함할지 (기본값 True)

        Returns:
            지원되면 True, 아니면 False

        Example:
            >>> # GenericCrawler 포함 (대부분의 웹사이트 지원)
            >>> CrawlerFactory.is_supported("https://example.com/article")
            True

            >>> # 전용 크롤러만 확인
            >>> CrawlerFactory.is_supported("https://example.com/article", include_generic=False)
            False

            >>> # 지원되지 않는 URL (YouTube 등)
            >>> CrawlerFactory.is_supported("https://youtube.com/watch?v=xxx")
            False
        """
        result = cls.detect_platform(url)

        if result["platform"] == "unsupported":
            return False

        if not include_generic and result["platform"] == "generic":
            return False

        return True

    @classmethod
    def register_crawler(
        cls, domain_pattern: str, crawler_cls: type[BaseCrawler]
    ) -> None:
        """
        새로운 크롤러를 등록합니다.

        런타임에 크롤러를 동적으로 추가할 때 사용합니다.

        Args:
            domain_pattern: 도메인 패턴 (예: "news.hada.io")
            crawler_cls: BaseCrawler를 상속한 크롤러 클래스

        Example:
            >>> class CustomCrawler(BaseCrawler):
            ...     platform_name = "custom"
            ...     # ... 구현 ...
            >>> CrawlerFactory.register_crawler("custom.com", CustomCrawler)
        """
        logger.info(f"크롤러 등록: {domain_pattern} → {crawler_cls.__name__}")
        cls._crawlers[domain_pattern] = crawler_cls
