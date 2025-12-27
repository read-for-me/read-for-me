"""
Generic Web Crawler

trafilatura 기반의 범용 웹 크롤러입니다.
지원하는 전용 크롤러(GeekNews, Medium)가 없는 모든 웹사이트에서
본문과 메타데이터를 추출합니다.

특징:
- trafilatura 라이브러리를 사용한 본문 추출
- OG 메타태그 기반 메타데이터 추출
- 한국어 사이트 최적화 (target_language="ko")
- BeautifulSoup fallback 로직

Usage:
    crawler = GenericCrawler()
    article = await crawler.extract("https://example.com/article")
"""

import re
from typing import Optional
from urllib.parse import urlparse

import trafilatura
from bs4 import BeautifulSoup
from loguru import logger

from app.services.crawlers.base import BaseCrawler
from app.services.crawlers.schemas import ArticleMetadata, CrawledArticle


class GenericCrawler(BaseCrawler):
    """
    범용 웹 크롤러
    
    trafilatura 라이브러리를 사용하여 다양한 웹사이트에서
    본문 텍스트와 메타데이터를 추출합니다.
    
    GeekNews, Medium 등 전용 크롤러가 없는 URL에 대해
    CrawlerFactory의 fallback으로 사용됩니다.
    """
    
    platform_name: str = "generic"
    
    # URL 유효성 검사 패턴 (HTTP/HTTPS)
    URL_PATTERN: str = r"^https?://.+"
    
    # 지원하지 않는 콘텐츠 타입 (주로 동적/멀티미디어 콘텐츠)
    UNSUPPORTED_DOMAINS: list[str] = [
        "youtube.com",
        "youtu.be",
        "vimeo.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "facebook.com",
        "tiktok.com",
        "linkedin.com",
    ]
    
    # 노이즈 요소 제거 선택자
    NOISE_SELECTORS: list[str] = [
        "script", "style", "noscript", "iframe",
        "nav", "header", "footer", "aside",
        ".sidebar", ".advertisement", ".ad", ".ads",
        ".social-share", ".comments", ".related-posts",
        ".nav", ".menu", ".navigation", ".breadcrumb",
        "[role='navigation']", "[role='banner']", "[role='complementary']",
    ]
    
    # 본문 추출 우선순위 선택자
    CONTENT_SELECTORS: list[str] = [
        "article",
        '[role="main"]',
        "main",
        ".post-content",
        ".article-content",
        ".article-body",
        ".entry-content",
        ".content",
        ".post-body",
        "#content",
        "#article",
        ".prose",  # Tailwind CSS 기반 사이트
        ".story-body",  # 뉴스 사이트
        ".news-content",
    ]
    
    def __init__(
        self,
        timeout: Optional[float] = None,
        headers: Optional[dict] = None,
        target_language: str = "ko",
    ):
        """
        Args:
            timeout: HTTP 요청 타임아웃 (초). 기본값 30초
            headers: 커스텀 HTTP 헤더
            target_language: 추출 대상 언어 (기본값 "ko" 한국어)
        """
        super().__init__(timeout=timeout, headers=headers)
        self.target_language = target_language
    
    # ─────────────────────────────────────────────────────────────────────────
    # 추상 메서드 구현
    # ─────────────────────────────────────────────────────────────────────────
    
    def validate_url(self, url: str) -> bool:
        """
        URL이 유효한 HTTP/HTTPS URL인지 검증합니다.
        
        지원하지 않는 도메인(YouTube, Twitter 등)은 제외됩니다.
        
        Args:
            url: 검증할 URL
            
        Returns:
            유효한 URL이면 True
        """
        # 기본 URL 패턴 검사
        if not re.match(self.URL_PATTERN, url):
            return False
        
        # 지원하지 않는 도메인 검사
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # www. 접두사 제거
            if domain.startswith("www."):
                domain = domain[4:]
            
            for unsupported in self.UNSUPPORTED_DOMAINS:
                if domain == unsupported or domain.endswith(f".{unsupported}"):
                    logger.warning(f"Unsupported domain for generic crawler: {domain}")
                    return False
            
            return True
        except Exception:
            return False
    
    async def extract(self, url: str) -> Optional[CrawledArticle]:
        """
        URL에서 콘텐츠를 추출합니다.
        
        크롤링 파이프라인:
        1. validate_url()로 URL 검증
        2. fetch_html()로 HTML 가져오기
        3. trafilatura로 본문 추출 (실패 시 BeautifulSoup fallback)
        4. OG 메타태그에서 메타데이터 추출
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            CrawledArticle 객체 또는 실패 시 None
        """
        # URL 유효성 검사
        if not self.validate_url(url):
            logger.error(f"Invalid URL for generic crawler: {url}")
            return None
        
        # HTML 가져오기
        html = await self.fetch_html(url)
        if html is None:
            logger.error(f"Failed to fetch HTML: {url}")
            return None
        
        # HTML 파싱
        soup = self.parse_html(html)
        
        # 콘텐츠 추출
        article = self._parse_content(soup, url, html)
        
        return article
    
    def _parse_content(
        self, 
        soup: BeautifulSoup, 
        url: str,
        html: Optional[str] = None,
    ) -> Optional[CrawledArticle]:
        """
        BeautifulSoup 및 trafilatura를 사용하여 콘텐츠를 추출합니다.
        
        Args:
            soup: BeautifulSoup 객체
            url: 원본 URL
            html: 원본 HTML 문자열 (trafilatura 추출용)
            
        Returns:
            CrawledArticle 객체 또는 실패 시 None
        """
        try:
            # 제목 추출
            title = self._extract_title(soup)
            
            # 본문 추출 (trafilatura 우선, fallback으로 BeautifulSoup)
            content = self._extract_content_with_trafilatura(html)
            
            if not content or len(content) < 100:
                logger.warning(
                    f"trafilatura extraction insufficient ({len(content) if content else 0} chars), "
                    f"trying BeautifulSoup fallback: {url}"
                )
                content = self._extract_content_fallback(soup)
            
            if not content:
                logger.warning(f"No content extracted from: {url}")
                return None
            
            # OG 메타데이터 추출
            og_meta = self.extract_og_meta(soup)
            
            # 추가 메타데이터 추출
            extra_meta = self._extract_extra_metadata(soup)
            
            # ArticleMetadata 생성
            metadata = self._build_metadata(
                og_meta,
                author=extra_meta.get("author"),
                published_at=extra_meta.get("published_at"),
            )
            
            # 제목 fallback: OG 제목 사용
            if not title and og_meta.get("og_title"):
                title = og_meta["og_title"]
            
            return CrawledArticle(
                title=title or "Untitled Article",
                content=content,
                url=url,
                platform=self.platform_name,
                metadata=metadata,
                secondary_urls=[],
            )
            
        except Exception as e:
            logger.error(f"Error parsing content from {url}: {e}")
            return None
    
    # ─────────────────────────────────────────────────────────────────────────
    # 제목 추출
    # ─────────────────────────────────────────────────────────────────────────
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """
        페이지에서 제목을 추출합니다.
        
        추출 우선순위:
        1. h1 태그
        2. og:title 메타 태그
        3. title 태그
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            추출된 제목 문자열
        """
        # 1. h1 태그
        h1_elem = soup.find("h1")
        if h1_elem:
            title = self.text_extractor.clean_text(h1_elem.get_text(strip=True))
            if title:
                return title
        
        # 2. og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return self.text_extractor.clean_text(og_title["content"])
        
        # 3. title 태그
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 일반적인 사이트명 구분자 제거 (| - : 등)
            title_text = re.split(r'\s*[|\-–—:]\s*', title_text)[0]
            return self.text_extractor.clean_text(title_text)
        
        return ""
    
    # ─────────────────────────────────────────────────────────────────────────
    # 본문 추출 (trafilatura)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _extract_content_with_trafilatura(self, html: Optional[str]) -> str:
        """
        trafilatura를 사용하여 본문을 추출합니다.
        
        Args:
            html: HTML 문자열
            
        Returns:
            추출된 본문 텍스트
        """
        if not html:
            return ""
        
        try:
            content = trafilatura.extract(
                html,
                include_comments=False,  # 댓글 제외
                include_tables=True,     # 테이블 포함
                no_fallback=False,       # fallback 알고리즘 사용
                favor_recall=True,       # 더 많은 콘텐츠 추출 선호
                target_language=self.target_language,  # 한국어 사이트 최적화
            )
            
            if content:
                return self.text_extractor.clean_text(content)
            
            return ""
            
        except Exception as e:
            logger.error(f"trafilatura extraction error: {e}")
            return ""
    
    # ─────────────────────────────────────────────────────────────────────────
    # 본문 추출 (BeautifulSoup Fallback)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _extract_content_fallback(self, soup: BeautifulSoup) -> str:
        """
        trafilatura 실패 시 BeautifulSoup을 사용한 fallback 본문 추출.
        
        일반적인 아티클 HTML 구조에서 본문을 추출합니다.
        GeekNewsCrawler의 _extract_content_fallback 로직을 재사용합니다.
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            추출된 텍스트 콘텐츠
        """
        try:
            # 노이즈 요소 제거
            clean_soup = self.text_extractor.remove_noise_elements(
                soup, self.NOISE_SELECTORS
            )
            
            # 본문 추출 우선순위에 따라 시도
            for selector in self.CONTENT_SELECTORS:
                content_elem = clean_soup.select_one(selector)
                if content_elem:
                    text = content_elem.get_text(separator="\n", strip=True)
                    if len(text) > 200:  # 최소 200자 이상이어야 유효
                        return self.text_extractor.clean_text(text)
            
            # Fallback: body 전체에서 추출
            body = clean_soup.find("body")
            if body:
                text = body.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return self.text_extractor.clean_text(text)
            
            return ""
            
        except Exception as e:
            logger.error(f"Error in fallback content extraction: {e}")
            return ""
    
    # ─────────────────────────────────────────────────────────────────────────
    # 메타데이터 추출
    # ─────────────────────────────────────────────────────────────────────────
    
    def _extract_extra_metadata(self, soup: BeautifulSoup) -> dict:
        """
        OG 태그 외의 추가 메타데이터를 추출합니다.
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            추가 메타데이터 딕셔너리
        """
        meta = {}
        
        # 작성자 추출 (다양한 패턴)
        author = self._extract_author(soup)
        if author:
            meta["author"] = author
        
        # 게시일 추출
        published_at = self._extract_published_date(soup)
        if published_at:
            meta["published_at"] = published_at
        
        return meta
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """
        작성자 정보를 추출합니다.
        
        다양한 메타 태그 및 HTML 요소에서 작성자를 찾습니다.
        """
        # 1. meta 태그
        author_meta_names = ["author", "article:author", "dc.creator", "dcterms.creator"]
        for name in author_meta_names:
            tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", property=name)
            if tag and tag.get("content"):
                return tag["content"]
        
        # 2. rel="author" 링크
        author_link = soup.find("a", rel="author")
        if author_link:
            return self.text_extractor.clean_text(author_link.get_text(strip=True))
        
        # 3. 일반적인 작성자 클래스
        author_selectors = [
            ".author", ".author-name", ".byline", ".writer",
            "[itemprop='author']", "[rel='author']",
        ]
        for selector in author_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = self.text_extractor.clean_text(elem.get_text(strip=True))
                if text and len(text) < 100:  # 너무 긴 텍스트는 제외
                    return text
        
        return None
    
    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[str]:
        """
        게시일을 추출합니다.
        
        다양한 메타 태그 및 HTML 요소에서 게시일을 찾습니다.
        """
        # 1. meta 태그
        date_meta_names = [
            "article:published_time", "datePublished", "date",
            "DC.date.issued", "dc.date", "pubdate",
        ]
        for name in date_meta_names:
            tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", property=name)
            if tag and tag.get("content"):
                return tag["content"]
        
        # 2. time 태그
        time_tag = soup.find("time")
        if time_tag:
            datetime_attr = time_tag.get("datetime")
            if datetime_attr:
                return datetime_attr
            return self.text_extractor.clean_text(time_tag.get_text(strip=True))
        
        # 3. JSON-LD에서 추출
        script_json = soup.find("script", type="application/ld+json")
        if script_json and script_json.string:
            try:
                import json
                data = json.loads(script_json.string)
                
                # 단일 객체 또는 배열 처리
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                if isinstance(data, dict):
                    for key in ["datePublished", "dateCreated", "dateModified"]:
                        if key in data:
                            return data[key]
            except (json.JSONDecodeError, IndexError):
                pass
        
        return None

