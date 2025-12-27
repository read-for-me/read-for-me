"""
GeekNews Base Crawler Module

GeekNews 크롤러들의 공통 기능을 정의합니다.
Weekly와 Article 크롤러가 이 클래스를 상속받습니다.
"""

import re
from abc import abstractmethod
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from loguru import logger

from base_crawler import BaseCrawler, BaseTextExtractor, CrawledContent


class GeekNewsBaseCrawler(BaseCrawler):
    """
    GeekNews 크롤러의 기본 클래스
    
    GeekNews의 공통 기능을 구현합니다:
    - URL 유효성 검사
    - 공통 메타데이터 추출
    - GeekNews 특화 텍스트 정리
    """
    
    platform_name: str = "geeknews"
    BASE_URL: str = "https://news.hada.io"
    
    # URL 패턴 정의 (하위 클래스에서 오버라이드)
    URL_PATTERN: str = r"https?://(www\.)?news\.hada\.io/.*"
    
    def __init__(
        self, 
        output_dir: str = "./output", 
        timeout: int = 30,
        save_local: bool = True,
        save_gcs: bool = False
    ):
        # BaseCrawler로 인자 전달
        super().__init__(
            output_dir=output_dir, 
            timeout=timeout,
            save_local=save_local,
            save_gcs=save_gcs
        )
        self.text_extractor = GeekNewsTextExtractor()
    
    def is_valid_url(self, url: str) -> bool:
        """
        GeekNews URL인지 확인합니다.
        
        Args:
            url: 확인할 URL
            
        Returns:
            유효한 GeekNews URL이면 True
        """
        return bool(re.match(self.URL_PATTERN, url))
    
    def extract(self, url: str) -> Optional[CrawledContent]:
        """
        URL에서 콘텐츠를 추출합니다.
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            CrawledContent 객체 또는 실패 시 None
        """
        # URL 유효성 검사
        if not self.is_valid_url(url):
            logger.error(f"Invalid URL for {self.__class__.__name__}: {url}")
            return None
        
        # HTML 가져오기
        html = self.fetch_html(url)
        if html is None:
            return None
        
        # HTML 파싱
        soup = self.parse_html(html)
        
        # 콘텐츠 추출
        return self._parse_content(soup, url)
    
    def _extract_og_meta(self, soup: BeautifulSoup) -> dict:
        """
        Open Graph 메타 태그에서 정보를 추출합니다.
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            메타 정보 딕셔너리
        """
        meta_info = {}
        
        og_tags = [
            ("og:title", "og_title"),
            ("og:description", "og_description"),
            ("og:url", "og_url"),
            ("og:image", "og_image"),
            ("article:published_time", "published_time"),
            ("article:author", "author"),
        ]
        
        for og_property, key in og_tags:
            tag = soup.find("meta", property=og_property)
            if tag and tag.get("content"):
                meta_info[key] = tag["content"]
        
        return meta_info
    
    @abstractmethod
    def _parse_content(self, soup: BeautifulSoup, url: str) -> Optional[CrawledContent]:
        """하위 클래스에서 구현"""
        pass


class GeekNewsTextExtractor(BaseTextExtractor):
    """GeekNews 특화 텍스트 추출기"""
    
    # 제거할 요소들의 선택자
    REMOVE_SELECTORS = [
        "script",
        "style",
        "nav",
        "header",
        "footer",
        ".liner-mini-tooltip",
        ".liner-mini-button",
        ".LImageHighlighter",
        ".grecaptcha-badge",
        ".comment_form",
        "form",
    ]
    
    def extract_main_content(self, soup: BeautifulSoup, content_selector: str) -> str:
        """
        메인 콘텐츠를 추출합니다.
        
        Args:
            soup: BeautifulSoup 객체
            content_selector: 콘텐츠 선택자
            
        Returns:
            추출된 텍스트
        """
        # 불필요한 요소 제거
        soup_copy = BeautifulSoup(str(soup), "html.parser")
        for selector in self.REMOVE_SELECTORS:
            for element in soup_copy.select(selector):
                element.decompose()
        
        # 콘텐츠 요소 찾기
        content_element = soup_copy.select_one(content_selector)
        if content_element is None:
            return ""
        
        return self.clean_text(self.extract_text_from_element(content_element))
    
    def extract_list_items(self, soup: BeautifulSoup, list_selector: str) -> list[dict]:
        """
        리스트 형태의 콘텐츠를 추출합니다.
        
        Args:
            soup: BeautifulSoup 객체
            list_selector: 리스트 선택자
            
        Returns:
            리스트 아이템 딕셔너리 목록
        """
        items = []
        list_element = soup.select_one(list_selector)
        
        if list_element is None:
            return items
        
        for li in list_element.select("li"):
            item = {}
            
            # 링크 추출
            link = li.select_one("a.link")
            if link:
                item["title"] = link.get_text(strip=True)
                item["url"] = link.get("href", "")
                if item["url"] and not item["url"].startswith("http"):
                    item["url"] = f"https://news.hada.io{item['url']}"
            
            # 설명 추출
            content_div = li.select_one(".content")
            if content_div:
                item["description"] = self.clean_text(content_div.get_text(strip=True))
            
            if item:
                items.append(item)
        
        return items