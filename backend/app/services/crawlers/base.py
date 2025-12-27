"""
Base Crawler Module

확장 가능한 웹 크롤러의 기본 추상 클래스를 정의합니다.
다양한 웹 소스(GeekNews, Medium 등)로 확장할 수 있도록 설계되었습니다.

주요 설계 결정:
- HTTP 클라이언트: httpx (async) - FastAPI 비동기 패턴과 호환
- 파일 저장 기능 제외 (MVP는 API 응답 중심)
"""

import re
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.services.crawlers.schemas import ArticleMetadata, CrawledArticle


class BaseTextExtractor:
    """
    HTML에서 텍스트를 추출하고 정제하는 유틸리티 클래스
    
    역할:
    - 공백/줄바꿈 정규화
    - 노이즈 요소(광고, 네비게이션 등) 제거
    """
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        텍스트를 정리합니다.
        - 3줄 이상 연속 줄바꿈 → 2줄로 정규화
        - 탭/연속 공백 → 스페이스 1개로 정규화
        - 각 줄의 앞뒤 공백 제거
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정리된 텍스트
        """
        if not text:
            return ""
        
        # 연속된 줄바꿈(3줄 이상) → 2줄로 정리
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 탭/연속 공백 → 스페이스 1개
        text = re.sub(r'[ \t]+', ' ', text)
        # 각 줄의 앞뒤 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()
    
    @staticmethod
    def remove_noise_elements(
        soup: BeautifulSoup, 
        selectors: list[str]
    ) -> BeautifulSoup:
        """
        광고, 네비게이션 등 노이즈 요소를 제거합니다.
        
        Args:
            soup: BeautifulSoup 객체
            selectors: 제거할 CSS 선택자 목록
            
        Returns:
            노이즈가 제거된 BeautifulSoup 객체 (원본을 수정하지 않음)
        """
        # 원본을 보존하기 위해 복사본 생성
        soup_copy = BeautifulSoup(str(soup), "html.parser")
        
        for selector in selectors:
            for element in soup_copy.select(selector):
                element.decompose()
        
        return soup_copy
    
    @staticmethod
    def extract_text_from_element(
        element, 
        separator: str = "\n"
    ) -> str:
        """
        BeautifulSoup 요소에서 텍스트를 추출합니다.
        
        Args:
            element: BeautifulSoup 요소
            separator: 텍스트 구분자
            
        Returns:
            추출된 텍스트
        """
        if element is None:
            return ""
        return element.get_text(separator=separator, strip=True)


class BaseCrawler(ABC):
    """
    모든 웹 크롤러의 추상 기본 클래스
    
    새로운 크롤러를 만들 때 이 클래스를 상속받아 구현합니다.
    GeekNews, Medium 등 다양한 플랫폼에 대응하는 서브클래스를 생성합니다.
    
    Usage:
        class GeekNewsCrawler(BaseCrawler):
            platform_name = "geeknews"
            
            def validate_url(self, url: str) -> bool:
                ...
            
            async def extract(self, url: str) -> CrawledArticle | None:
                ...
            
            def _parse_content(self, soup, url) -> CrawledArticle | None:
                ...
    """
    
    # 클래스 변수: 플랫폼 식별자 (하위 클래스에서 오버라이드)
    platform_name: str = "base"
    
    # 기본 요청 헤더
    DEFAULT_HEADERS: dict = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    # 기본 HTTP 타임아웃 (초)
    DEFAULT_TIMEOUT: float = 30.0
    
    def __init__(
        self,
        timeout: Optional[float] = None,
        headers: Optional[dict] = None,
    ):
        """
        Args:
            timeout: HTTP 요청 타임아웃 (초). 기본값 30초
            headers: 커스텀 HTTP 헤더. 기본값은 DEFAULT_HEADERS
        """
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.headers = headers or self.DEFAULT_HEADERS.copy()
        self.text_extractor = BaseTextExtractor()
    
    # ─────────────────────────────────────────────────────────────────────────
    # 공통 메서드 (구현됨)
    # ─────────────────────────────────────────────────────────────────────────
    
    async def fetch_html(self, url: str) -> Optional[str]:
        """
        URL에서 HTML을 비동기로 가져옵니다.
        
        httpx를 사용하여 FastAPI 비동기 패턴과 호환됩니다.
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            HTML 문자열 또는 실패 시 None
        """
        try:
            logger.info(f"Fetching HTML from: {url}")
            
            async with httpx.AsyncClient(
                timeout=self.timeout, 
                headers=self.headers,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # httpx는 자동으로 인코딩을 처리함
                return response.text
                
        except httpx.TimeoutException:
            logger.error(f"Timeout while fetching {url}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            return None
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """
        HTML을 BeautifulSoup 객체로 파싱합니다.
        
        Args:
            html: HTML 문자열
            
        Returns:
            BeautifulSoup 객체
        """
        return BeautifulSoup(html, "html.parser")
    
    def extract_og_meta(self, soup: BeautifulSoup) -> dict:
        """
        Open Graph 메타 태그에서 정보를 추출합니다.
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            OG 메타 정보 딕셔너리
        """
        meta_info = {}
        
        # 추출할 OG 태그 매핑 (og_property -> dict_key)
        og_tags = [
            ("og:title", "og_title"),
            ("og:description", "og_description"),
            ("og:url", "og_url"),
            ("og:image", "og_image"),
            ("article:published_time", "published_at"),
            ("article:author", "author"),
        ]
        
        for og_property, key in og_tags:
            tag = soup.find("meta", property=og_property)
            if tag and tag.get("content"):
                meta_info[key] = tag["content"]
        
        return meta_info
    
    def _build_metadata(self, og_meta: dict, **extra_fields) -> ArticleMetadata:
        """
        OG 메타 정보와 추가 필드를 결합하여 ArticleMetadata를 생성합니다.
        
        Args:
            og_meta: extract_og_meta()에서 추출한 딕셔너리
            **extra_fields: 추가 메타데이터 필드
            
        Returns:
            ArticleMetadata 인스턴스
        """
        combined = {**og_meta, **extra_fields}
        return ArticleMetadata(**combined)
    
    # ─────────────────────────────────────────────────────────────────────────
    # 추상 메서드 (하위 클래스에서 구현 필수)
    # ─────────────────────────────────────────────────────────────────────────
    
    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """
        URL이 해당 플랫폼에 유효한지 검증합니다.
        
        Args:
            url: 검증할 URL
            
        Returns:
            유효한 URL이면 True, 아니면 False
        """
        pass
    
    @abstractmethod
    async def extract(self, url: str) -> Optional[CrawledArticle]:
        """
        URL에서 콘텐츠를 추출합니다. (1차 페이지)
        
        전체 크롤링 파이프라인:
        1. validate_url()로 URL 검증
        2. fetch_html()로 HTML 가져오기
        3. parse_html()로 BeautifulSoup 파싱
        4. _parse_content()로 구조화된 데이터 추출
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            CrawledArticle 객체 또는 실패 시 None
        """
        pass
    
    @abstractmethod
    def _parse_content(
        self, 
        soup: BeautifulSoup, 
        url: str
    ) -> Optional[CrawledArticle]:
        """
        BeautifulSoup에서 구조화된 데이터를 추출합니다.
        
        플랫폼별 DOM 구조에 맞게 구현합니다:
        - 제목 추출
        - 본문 추출
        - 메타데이터 추출
        
        Args:
            soup: BeautifulSoup 객체
            url: 원본 URL
            
        Returns:
            CrawledArticle 객체 또는 실패 시 None
        """
        pass
    
    # ─────────────────────────────────────────────────────────────────────────
    # 2차 URL 크롤링 (stub - 추후 구현)
    # ─────────────────────────────────────────────────────────────────────────
    
    def extract_secondary_urls(self, soup: BeautifulSoup) -> list[str]:
        """
        2차 URL 목록을 추출합니다.
        
        GeekNews처럼 원본 링크를 포함하는 플랫폼에서 사용합니다.
        기본 구현은 빈 리스트를 반환합니다.
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            2차 URL 목록 (기본: 빈 리스트)
        """
        return []
    
    async def crawl_secondary(self, urls: list[str]) -> list[CrawledArticle]:
        """
        2차 URL들을 크롤링합니다.
        
        현재는 미구현 상태입니다. 추후 확장 시 구현 예정.
        
        Args:
            urls: 크롤링할 URL 목록
            
        Returns:
            CrawledArticle 목록
            
        Raises:
            NotImplementedError: 아직 구현되지 않음
        """
        raise NotImplementedError("Secondary URL crawling is not yet implemented")
