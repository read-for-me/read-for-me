"""
Medium Article Crawler

Medium 아티클 페이지를 크롤링합니다.
BaseCrawler를 상속받아 FastAPI 비동기 패턴과 호환됩니다.

미러 서비스를 통해 전체 콘텐츠(페이월 포함)를 가져옵니다.
- Freedium: https://freedium.cfd/{medium_url}
- Scribe.rip: https://scribe.rip/{path}
- trafilatura fallback: 원본 URL에서 직접 추출

URL 형식:
- https://medium.com/@username/article-title-xxxxx
- https://medium.com/publication/article-title-xxxxx
- 커스텀 도메인 (meta 태그로 Medium 여부 확인)

Usage:
    crawler = MediumCrawler()
    article = await crawler.extract("https://medium.com/@user/article")
"""

import asyncio
import json
import re
from urllib.parse import urlparse

import trafilatura
from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from app.services.crawlers.base import BaseCrawler, BaseTextExtractor
from app.services.crawlers.schemas import CrawledArticle


class MediumTextExtractor(BaseTextExtractor):
    """
    Medium/Freedium 페이지 특화 텍스트 추출기

    불필요한 UI 요소를 제거합니다.
    """

    REMOVE_SELECTORS = [
        "script",
        "style",
        "noscript",
        "iframe",
        "nav",
        "footer",
        "button",
        "header",
        ".sidebar",
        ".ad",
        ".advertisement",
        "[data-testid='headerSignUpButton']",
        "[data-testid='headerSignInButton']",
        ".speechify-ignore",
        ".grecaptcha-badge",
    ]

    # Freedium 노이즈 텍스트 패턴 (이 텍스트가 포함된 요소와 그 이후 형제 요소를 제거)
    FREEDIUM_NOISE_TEXTS = [
        "Reporting a Problem",
        "Sometimes we have problems displaying some Medium posts",
        "fucking Cloudflare",
    ]

    def clean_html(self, soup: BeautifulSoup) -> BeautifulSoup:
        """HTML에서 노이즈 요소를 제거합니다."""
        soup_copy = BeautifulSoup(str(soup), "html.parser")

        # 1. 셀렉터 기반 노이즈 제거
        for selector in self.REMOVE_SELECTORS:
            for element in soup_copy.select(selector):
                element.decompose()

        # 2. Freedium 텍스트 기반 노이즈 제거
        for noise_text in self.FREEDIUM_NOISE_TEXTS:
            for tag in soup_copy.find_all(["h1", "h2", "h3", "p"]):
                if noise_text in tag.get_text():
                    # 해당 태그와 그 뒤의 모든 형제 요소 제거
                    for sibling in list(tag.find_next_siblings()):
                        sibling.decompose()
                    tag.decompose()
                    break  # 해당 패턴은 한 번만 제거

        return soup_copy


class MediumCrawler(BaseCrawler):
    """
    Medium Article 크롤러 (Multi-Mirror 기반)

    여러 미러 서비스를 통해 Medium 아티클의 전체 콘텐츠를 가져옵니다.
    - Freedium: 봇 탐지 우회, 페이월 콘텐츠 접근
    - Scribe.rip: Freedium 대안, 깔끔한 HTML 구조
    - trafilatura: 최후의 fallback, 원본 URL에서 직접 추출

    개별 아티클 페이지에서 다음 정보를 추출합니다:
    - 제목 및 부제목
    - 작성자 정보
    - 게시일 및 읽는 시간
    - 본문 내용 (코드블록, 인용구, 리스트 보존)
    """

    platform_name: str = "medium"

    # 미러 서비스 목록 (우선순위 순)
    MIRROR_SERVICES: list[tuple[str, str]] = [
        ("freedium", "https://freedium.cfd"),
        ("scribe", "https://scribe.rip"),
    ]

    # Freedium 미러 사이트 URL (호환성 유지)
    FREEDIUM_BASE_URL: str = "https://freedium.cfd"

    # Medium 표준 URL 패턴
    URL_PATTERNS: list[str] = [
        r"https?://(www\.)?medium\.com/.+",
        r"https?://[a-zA-Z0-9-]+\.medium\.com/.+",
    ]

    # HTTP 헤더
    DEFAULT_HEADERS: dict = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    }

    # 기본 요청 지연 (초) - Rate limiting 방지
    DEFAULT_REQUEST_DELAY: float = 0.5

    def __init__(
        self,
        timeout: float | None = None,
        headers: dict | None = None,
        request_delay: float | None = None,
        use_freedium: bool = True,
    ):
        """
        Args:
            timeout: HTTP 요청 타임아웃 (초). 기본값 30초
            headers: 커스텀 HTTP 헤더
            request_delay: 요청 전 지연 시간 (초). 기본값 0.5초
            use_freedium: Freedium 미러 사이트 사용 여부 (기본값 True)
        """
        super().__init__(timeout=timeout, headers=headers or self.DEFAULT_HEADERS)
        self.text_extractor = MediumTextExtractor()
        self.request_delay = (
            request_delay if request_delay is not None else self.DEFAULT_REQUEST_DELAY
        )
        self.use_freedium = use_freedium

    # ─────────────────────────────────────────────────────────────────────────
    # URL 변환 및 검증
    # ─────────────────────────────────────────────────────────────────────────

    def _convert_to_mirror_url(self, url: str, service: str) -> str:
        """
        Medium URL을 미러 서비스 URL로 변환합니다.

        Args:
            url: 원본 Medium URL
            service: 미러 서비스 이름 ('freedium', 'scribe')

        Returns:
            변환된 미러 URL
        """
        parsed = urlparse(url)
        path = parsed.path  # /@username/article-title-xxx

        if service == "freedium":
            return f"https://freedium.cfd/{url}"
        elif service == "scribe":
            # Scribe.rip은 경로만 사용
            # https://medium.com/@user/article -> https://scribe.rip/@user/article
            return f"https://scribe.rip{path}"

        return url

    def _convert_to_freedium_url(self, url: str) -> str:
        """
        Medium URL을 Freedium URL로 변환합니다. (호환성 유지)

        Args:
            url: 원본 Medium URL

        Returns:
            Freedium URL (예: https://freedium.cfd/https://medium.com/...)
        """
        return self._convert_to_mirror_url(url, "freedium")

    def _extract_original_url(self, mirror_url: str) -> str:
        """
        미러 URL에서 원본 Medium URL을 추출합니다.

        Args:
            mirror_url: Freedium 또는 Scribe URL

        Returns:
            원본 Medium URL
        """
        # Freedium URL 처리
        if mirror_url.startswith(self.FREEDIUM_BASE_URL + "/"):
            return mirror_url[len(self.FREEDIUM_BASE_URL) + 1 :]

        # Scribe URL 처리
        if mirror_url.startswith("https://scribe.rip/"):
            path = mirror_url[len("https://scribe.rip") :]
            return f"https://medium.com{path}"

        return mirror_url

    def validate_url(self, url: str) -> bool:
        """
        URL이 Medium 아티클 URL인지 검증합니다.

        Args:
            url: 검증할 URL

        Returns:
            유효한 Medium URL이면 True
        """
        # Freedium URL인 경우 원본 URL 추출
        check_url = self._extract_original_url(url)

        for pattern in self.URL_PATTERNS:
            if re.match(pattern, check_url):
                return True
        return False

    def _parse_content(self, soup: BeautifulSoup, url: str) -> CrawledArticle | None:
        """
        BeautifulSoup에서 아티클 데이터를 추출합니다.

        BaseCrawler 추상 메서드 구현.
        기본적으로 Freedium 파싱 로직을 사용합니다.

        Args:
            soup: BeautifulSoup 객체
            url: 원본 URL

        Returns:
            CrawledArticle 객체 또는 실패 시 None
        """
        return self._parse_freedium_content(soup, url)

    # ─────────────────────────────────────────────────────────────────────────
    # 크롤링 메서드
    # ─────────────────────────────────────────────────────────────────────────

    async def extract(self, url: str) -> CrawledArticle | None:
        """
        Medium 아티클 URL에서 콘텐츠를 추출합니다.

        전체 크롤링 파이프라인:
        1. validate_url()로 URL 검증
        2. 요청 지연 (rate limiting 방지)
        3. 미러 서비스 순차 시도 (Freedium → Scribe.rip)
        4. 모든 미러 실패 시 trafilatura fallback
        5. _parse_content()로 구조화된 데이터 추출

        Args:
            url: 크롤링할 Medium 아티클 URL

        Returns:
            CrawledArticle 객체 또는 실패 시 None
        """
        # 원본 URL 저장 (결과에 사용)
        original_url = self._extract_original_url(url)

        # URL 패턴 검사
        if not self.validate_url(url):
            logger.warning(f"URL pattern doesn't match Medium format: {url}")

        # 요청 지연 (rate limiting 방지)
        if self.request_delay > 0:
            logger.debug(f"Request delay: {self.request_delay}초 대기 중...")
            await asyncio.sleep(self.request_delay)

        # 미러 서비스 사용이 활성화된 경우
        if self.use_freedium:
            # 각 미러 서비스 순차 시도
            for service_name, _base_url in self.MIRROR_SERVICES:
                mirror_url = self._convert_to_mirror_url(original_url, service_name)
                logger.info(f"{service_name}을 통해 시도: {mirror_url}")

                html = await self.fetch_html(mirror_url)

                # HTML이 유효한지 검증 (최소 길이, 에러 페이지 아님)
                if html and len(html) > 1000 and not self._is_error_page(html):
                    logger.info(f"✅ {service_name} 성공! ({len(html):,} bytes)")
                    soup = self.parse_html(html)

                    # 서비스별 파싱 로직 분기
                    if service_name == "freedium":
                        result = self._parse_freedium_content(soup, original_url)
                    elif service_name == "scribe":
                        result = self._parse_scribe_content(soup, original_url)
                    else:
                        result = self._parse_freedium_content(soup, original_url)

                    if result and len(result.content) > 100:
                        return result
                    else:
                        logger.warning(
                            f"{service_name} 파싱 결과 불충분, 다음 서비스 시도..."
                        )
                else:
                    logger.warning(f"❌ {service_name} 실패, 다음 서비스 시도...")

        # 모든 미러 실패 시 trafilatura fallback
        logger.info("모든 미러 서비스 실패, trafilatura fallback 시도...")
        result = await self._extract_with_trafilatura(original_url)
        if result:
            return result

        # 최후의 수단 1: 원본 Medium URL에서 직접 파싱
        logger.info(f"trafilatura 실패, 원본 Medium URL 직접 파싱 시도: {original_url}")
        html = await self.fetch_html(original_url)
        if html:
            soup = self.parse_html(html)
            result = self._parse_medium_content(soup, original_url)
            if result and len(result.content) > 100:
                return result

        # 최후의 수단 2: Playwright 동적 렌더링
        logger.info("모든 정적 방법 실패, Playwright 동적 렌더링 시도...")
        result = await self._extract_with_playwright(original_url)
        if result:
            return result

        logger.error(f"모든 방법 실패 (미러 + trafilatura + Playwright): {url}")
        return None

    def _is_error_page(self, html: str) -> bool:
        """HTML이 에러 페이지인지 확인"""
        error_indicators = [
            "404 Not Found",
            "Page not found",
            "Error 404",
            "We couldn't find",
            "This page doesn't exist",
            "Access denied",
            "403 Forbidden",
            "PAGE NOT FOUND",  # Medium 404 페이지
            "Out of nothing, something",  # Medium 404 페이지 문구
        ]
        html_lower = html.lower()
        return any(indicator.lower() in html_lower for indicator in error_indicators)

    def _is_404_content(self, content: str) -> bool:
        """추출된 콘텐츠가 404 페이지 내용인지 확인"""
        if not content:
            return True

        content_lower = content.lower()
        error_indicators = [
            "page not found",
            "404",
            "out of nothing, something",  # Medium 404 페이지 특유 문구
            "you can find (just about) anything on medium",
        ]

        # 처음 500자에 에러 표시가 있으면 404 페이지
        first_part = content_lower[:500]
        return any(indicator in first_part for indicator in error_indicators)

    # ─────────────────────────────────────────────────────────────────────────
    # Freedium 파싱
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_freedium_content(
        self, soup: BeautifulSoup, url: str
    ) -> CrawledArticle | None:
        """
        Freedium HTML에서 아티클 데이터를 추출합니다.

        Freedium은 Medium 콘텐츠를 정제된 형태로 제공합니다.
        """
        try:
            # 노이즈 제거
            clean_soup = self.text_extractor.clean_html(soup)

            # 제목 추출
            title = self._extract_freedium_title(clean_soup)

            # 메타데이터 추출
            meta_info = self._extract_freedium_metadata(clean_soup)

            # 본문 추출
            article_body = self._extract_freedium_body(clean_soup)

            # 전체 콘텐츠 조합
            content = self._build_content(meta_info, article_body)

            # ArticleMetadata 생성
            metadata = self._build_metadata(
                {},  # OG 메타는 Freedium에서 제공되지 않음
                author=meta_info.get("author"),
                published_at=meta_info.get("date"),
                read_time=meta_info.get("read_time"),
                subtitle=meta_info.get("subtitle"),
            )

            return CrawledArticle(
                title=title or "Untitled Medium Article",
                content=content,
                url=url,
                platform=self.platform_name,
                metadata=metadata,
                secondary_urls=[],
            )

        except Exception as e:
            logger.error(f"Error parsing Freedium content: {e}")
            return None

    def _extract_freedium_title(self, soup: BeautifulSoup) -> str | None:
        """Freedium에서 제목 추출"""
        # h1 태그에서 제목 추출
        title_elem = soup.select_one("h1")
        if title_elem:
            return self.text_extractor.clean_text(title_elem.get_text())

        # fallback: title 태그
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text()
            # " - Freedium" 접미사 제거
            if " - Freedium" in title_text:
                title_text = title_text.replace(" - Freedium", "")
            return self.text_extractor.clean_text(title_text)

        return None

    def _extract_freedium_metadata(self, soup: BeautifulSoup) -> dict:
        """Freedium에서 메타데이터 추출"""
        meta = {}

        # 작성자 (보통 첫 번째 링크나 특정 클래스)
        author_elem = soup.select_one('.author, [rel="author"], a[href*="/@"]')
        if author_elem:
            meta["author"] = self.text_extractor.clean_text(author_elem.get_text())

        # 부제목 (h1 다음의 h2 또는 특정 클래스)
        subtitle_elem = soup.select_one("h2, .subtitle")
        if subtitle_elem:
            subtitle_text = self.text_extractor.clean_text(subtitle_elem.get_text())
            # 부제목이 너무 길지 않은 경우에만 사용 (본문 h2와 구분)
            if len(subtitle_text) < 200:
                meta["subtitle"] = subtitle_text

        # 날짜 추출 (time 태그 또는 날짜 패턴)
        time_elem = soup.select_one("time")
        if time_elem:
            meta["date"] = time_elem.get("datetime") or time_elem.get_text(strip=True)

        return meta

    def _extract_freedium_body(self, soup: BeautifulSoup) -> str:
        """Freedium에서 본문 추출"""
        # Freedium은 main 또는 article 태그에 본문을 넣음
        article_content = (
            soup.select_one("main")
            or soup.select_one("article")
            or soup.select_one(".content")
            or soup.select_one("body")
        )

        if not article_content:
            return ""

        content_parts = []

        # 모든 의미 있는 태그 순회
        tags = article_content.find_all(
            [
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "blockquote",
                "pre",
                "ul",
                "ol",
                "figure",
                "img",
            ]
        )

        seen_texts = set()  # 중복 제거용

        for tag in tags:
            text_content = self._format_tag(tag)
            if text_content and text_content not in seen_texts:
                content_parts.append(text_content)
                seen_texts.add(text_content)

        return "\n".join(content_parts)

    def _format_tag(self, tag) -> str | None:
        """태그를 마크다운 형식으로 변환"""
        if tag.name == "figure" or tag.name == "img":
            img = tag if tag.name == "img" else tag.find("img")
            if img:
                alt_text = img.get("alt", "")
                src = img.get("src", "")
                caption = tag.find("figcaption") if tag.name == "figure" else None
                caption_text = caption.get_text(strip=True) if caption else ""

                result = f"\n[Image: {alt_text}]({src})"
                if caption_text:
                    result += f"\n  └─ <caption>: {caption_text}"
                return result
            return None

        if tag.name == "pre":
            code_text = tag.get_text(separator="\n", strip=True)
            return f"\n```\n{code_text}\n```\n"

        if tag.name == "blockquote":
            quote_text = self.text_extractor.clean_text(tag.get_text())
            return f"\n> {quote_text}\n"

        if tag.name in ["ul", "ol"]:
            items = []
            for idx, li in enumerate(tag.find_all("li", recursive=False), 1):
                marker = "-" if tag.name == "ul" else f"{idx}."
                li_text = self.text_extractor.clean_text(li.get_text())
                items.append(f"{marker} {li_text}")
            return "\n".join(items) + "\n" if items else None

        if tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = int(tag.name[1])
            text = self.text_extractor.clean_text(tag.get_text())
            return f"\n{'#' * level} {text}\n" if text else None

        # 일반 문단 (p)
        text = self.text_extractor.clean_text(tag.get_text())
        return text if text else None

    # ─────────────────────────────────────────────────────────────────────────
    # Medium 원본 파싱 (Fallback)
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_medium_content(
        self, soup: BeautifulSoup, url: str
    ) -> CrawledArticle | None:
        """
        원본 Medium HTML에서 아티클 데이터를 추출합니다 (Fallback).

        Medium은 JavaScript 렌더링을 사용하므로 일부 콘텐츠만 추출될 수 있습니다.
        """
        try:
            clean_soup = self.text_extractor.clean_html(soup)

            # 메타데이터 추출
            meta_info = self._extract_medium_metadata(clean_soup)

            # 본문 추출
            article_body = self._extract_medium_body(clean_soup)

            # 전체 콘텐츠 조합
            content = self._build_content(meta_info, article_body)

            # 제목 결정
            title = meta_info.get("title", "Untitled Medium Article")

            # OG 메타데이터 추출
            og_meta = self.extract_og_meta(soup)

            # ArticleMetadata 생성
            metadata = self._build_metadata(
                og_meta,
                author=meta_info.get("author"),
                published_at=meta_info.get("date"),
                read_time=meta_info.get("read_time"),
                claps=meta_info.get("claps"),
                tags=meta_info.get("tags"),
                subtitle=meta_info.get("subtitle"),
            )

            return CrawledArticle(
                title=title,
                content=content,
                url=url,
                platform=self.platform_name,
                metadata=metadata,
                secondary_urls=[],
            )

        except Exception as e:
            logger.error(f"Error parsing Medium content: {e}")
            return None

    def _extract_medium_metadata(self, soup: BeautifulSoup) -> dict:
        """원본 Medium에서 메타데이터 추출"""
        meta = {}

        # 제목
        title_elem = soup.select_one('[data-testid="storyTitle"]') or soup.select_one(
            "h1"
        )
        if title_elem:
            meta["title"] = self.text_extractor.clean_text(title_elem.get_text())
        else:
            title_tag = soup.find("title")
            if title_tag:
                meta["title"] = self.text_extractor.clean_text(title_tag.get_text())

        # 부제목
        subtitle_elem = soup.select_one(".pw-subtitle-paragraph")
        if subtitle_elem:
            meta["subtitle"] = self.text_extractor.clean_text(subtitle_elem.get_text())

        # 작성자
        author_elem = soup.select_one('[data-testid="authorName"]')
        if author_elem:
            meta["author"] = self.text_extractor.clean_text(author_elem.get_text())

        # 게시일
        date_elem = soup.select_one('[data-testid="storyPublishDate"]')
        if date_elem:
            meta["date"] = self.text_extractor.clean_text(date_elem.get_text())

        # 읽는 시간
        read_time_elem = soup.select_one('[data-testid="storyReadTime"]')
        if read_time_elem:
            meta["read_time"] = self.text_extractor.clean_text(
                read_time_elem.get_text()
            )

        # 박수 수
        clap_elem = soup.select_one(
            '[data-testid="headerClapButton"]'
        ) or soup.select_one('[data-testid="footerClapButton"]')
        if clap_elem:
            clap_text = clap_elem.get_text(strip=True)
            meta["claps"] = re.sub(r"[^0-9K.]", "", clap_text)

        # JSON-LD에서 태그 추출
        script_json = soup.find("script", type="application/ld+json")
        if script_json and script_json.string:
            try:
                data = json.loads(script_json.string)
                if isinstance(data, dict) and "keywords" in data:
                    keywords = data["keywords"]
                    if isinstance(keywords, list):
                        meta["tags"] = keywords
                    elif isinstance(keywords, str):
                        meta["tags"] = [k.strip() for k in keywords.split(",")]
            except json.JSONDecodeError:
                pass

        return meta

    def _extract_medium_body(self, soup: BeautifulSoup) -> str:
        """원본 Medium에서 본문 추출"""
        article_content = soup.select_one("section") or soup.select_one("article")

        if not article_content:
            return ""

        content_parts = []

        tags = article_content.find_all(
            [
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "blockquote",
                "pre",
                "ul",
                "ol",
                "figure",
            ]
        )

        for tag in tags:
            text_content = self._format_tag(tag)
            if text_content:
                content_parts.append(text_content)

        return "\n".join(content_parts)

    # ─────────────────────────────────────────────────────────────────────────
    # 공통 유틸리티
    # ─────────────────────────────────────────────────────────────────────────

    def _build_content(self, meta_info: dict, article_body: str) -> str:
        """추출된 데이터를 하나의 콘텐츠 문자열로 조합"""
        content_parts = []

        # 부제목
        if meta_info.get("subtitle"):
            content_parts.append(f"📝 Subtitle: {meta_info['subtitle']}")
            content_parts.append("")

        # 메타 정보 라인
        info_items = []
        if meta_info.get("author"):
            info_items.append(f"Author: {meta_info['author']}")
        if meta_info.get("date"):
            info_items.append(f"Date: {meta_info['date']}")
        if meta_info.get("read_time"):
            info_items.append(f"Read Time: {meta_info['read_time']}")
        if meta_info.get("claps"):
            info_items.append(f"👏 Claps: {meta_info['claps']}")

        if info_items:
            content_parts.append(" | ".join(info_items))
            content_parts.append("-" * 40)
            content_parts.append("")

        # 본문
        if article_body:
            content_parts.append(article_body)

        # 태그
        if meta_info.get("tags"):
            content_parts.append("")
            content_parts.append("-" * 40)
            content_parts.append(f"🏷️ Tags: {', '.join(meta_info['tags'])}")

        return "\n".join(content_parts)

    # ─────────────────────────────────────────────────────────────────────────
    # Scribe.rip 파싱
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_scribe_content(
        self, soup: BeautifulSoup, url: str
    ) -> CrawledArticle | None:
        """
        Scribe.rip HTML에서 아티클 데이터를 추출합니다.

        Scribe.rip은 깔끔한 HTML 구조를 제공합니다.
        """
        try:
            # 노이즈 제거
            clean_soup = self.text_extractor.clean_html(soup)

            # 제목 추출
            title = self._extract_scribe_title(clean_soup)

            # 메타데이터 추출
            meta_info = self._extract_scribe_metadata(clean_soup)

            # 본문 추출
            article_body = self._extract_scribe_body(clean_soup)

            # 전체 콘텐츠 조합
            content = self._build_content(meta_info, article_body)

            # ArticleMetadata 생성
            metadata = self._build_metadata(
                {},
                author=meta_info.get("author"),
                published_at=meta_info.get("date"),
                read_time=meta_info.get("read_time"),
                subtitle=meta_info.get("subtitle"),
            )

            return CrawledArticle(
                title=title or "Untitled Medium Article",
                content=content,
                url=url,
                platform=self.platform_name,
                metadata=metadata,
                secondary_urls=[],
            )

        except Exception as e:
            logger.error(f"Error parsing Scribe content: {e}")
            return None

    def _extract_scribe_title(self, soup: BeautifulSoup) -> str | None:
        """Scribe.rip에서 제목 추출"""
        # article 내의 h1 우선
        article = soup.select_one("article")
        if article:
            title_elem = article.select_one("h1")
            if title_elem:
                return self.text_extractor.clean_text(title_elem.get_text())

        # fallback: 전체에서 h1
        title_elem = soup.select_one("h1")
        if title_elem:
            return self.text_extractor.clean_text(title_elem.get_text())

        # fallback: title 태그
        title_tag = soup.find("title")
        if title_tag:
            return self.text_extractor.clean_text(title_tag.get_text())

        return None

    def _extract_scribe_metadata(self, soup: BeautifulSoup) -> dict:
        """Scribe.rip에서 메타데이터 추출"""
        meta = {}

        # 작성자 (a 태그에서 @username 패턴)
        author_links = soup.select('a[href*="/@"]')
        for link in author_links:
            text = link.get_text(strip=True)
            if text and not text.startswith("http"):
                meta["author"] = text
                break

        # 날짜 (time 태그 또는 datetime 속성)
        time_elem = soup.select_one("time")
        if time_elem:
            meta["date"] = time_elem.get("datetime") or time_elem.get_text(strip=True)

        # 읽는 시간 (보통 "X min read" 패턴)
        for elem in soup.find_all(["span", "p", "div"]):
            text = elem.get_text(strip=True)
            if re.match(r"\d+\s*min\s*read", text, re.IGNORECASE):
                meta["read_time"] = text
                break

        return meta

    def _extract_scribe_body(self, soup: BeautifulSoup) -> str:
        """Scribe.rip에서 본문 추출"""
        # article 태그 우선
        article_content = (
            soup.select_one("article")
            or soup.select_one("main")
            or soup.select_one(".content")
            or soup.select_one("body")
        )

        if not article_content:
            return ""

        content_parts = []
        seen_texts = set()  # 중복 제거용

        # 모든 의미 있는 태그 순회
        tags = article_content.find_all(
            [
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "blockquote",
                "pre",
                "ul",
                "ol",
                "figure",
                "img",
            ]
        )

        for tag in tags:
            text_content = self._format_tag(tag)
            if text_content and text_content not in seen_texts:
                content_parts.append(text_content)
                seen_texts.add(text_content)

        return "\n".join(content_parts)

    # ─────────────────────────────────────────────────────────────────────────
    # trafilatura Fallback
    # ─────────────────────────────────────────────────────────────────────────

    async def _extract_with_trafilatura(self, url: str) -> CrawledArticle | None:
        """
        trafilatura를 사용하여 원본 Medium URL에서 직접 콘텐츠 추출을 시도합니다.

        미러 서비스가 모두 실패했을 때 fallback으로 사용됩니다.
        """
        try:
            html = await self.fetch_html(url)
            if not html:
                logger.warning(f"trafilatura: HTML 가져오기 실패 - {url}")
                return None

            # trafilatura로 본문 추출
            content = trafilatura.extract(
                html,
                favor_recall=True,  # 더 많은 콘텐츠 추출 우선
                include_comments=False,
                include_tables=True,
            )

            if not content or len(content) < 100:
                logger.warning(f"trafilatura: 콘텐츠 추출 실패 또는 불충분 - {url}")
                return None

            logger.info(f"✅ trafilatura 성공! ({len(content):,} 자)")

            # OG 메타데이터 추출
            soup = self.parse_html(html)
            og_meta = self.extract_og_meta(soup)

            # 제목 결정 (OG 태그 또는 title 태그)
            title = og_meta.get("og_title")
            if not title:
                title_tag = soup.find("title")
                if title_tag:
                    title = self.text_extractor.clean_text(title_tag.get_text())

            # ArticleMetadata 생성
            metadata = self._build_metadata(og_meta)

            return CrawledArticle(
                title=title or "Medium Article",
                content=content,
                url=url,
                platform=self.platform_name,
                metadata=metadata,
                secondary_urls=[],
            )

        except Exception as e:
            logger.error(f"trafilatura extraction error: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Playwright Fallback (동적 렌더링)
    # ─────────────────────────────────────────────────────────────────────────

    async def _extract_with_playwright(self, url: str) -> CrawledArticle | None:
        """
        Playwright를 사용하여 브라우저에서 동적으로 렌더링된 콘텐츠를 추출합니다.

        모든 미러 서비스와 trafilatura가 실패했을 때 최후의 fallback으로 사용됩니다.
        - 실제 브라우저 환경 시뮬레이션
        - JavaScript 렌더링 대기
        - 봇 탐지 우회 가능성 높음
        """
        logger.info(f"🎭 Playwright 동적 렌더링 시도: {url}")

        try:
            async with async_playwright() as p:
                # Chromium 브라우저 실행 (headless 모드)
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ],
                )

                # 브라우저 컨텍스트 설정 (실제 사용자처럼 보이게)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                )

                page = await context.new_page()

                # 페이지 로드 (네트워크 안정화까지 대기)
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                except PlaywrightTimeout:
                    logger.warning(
                        "Playwright: 페이지 로드 타임아웃, 부분 콘텐츠로 진행..."
                    )

                # 추가 대기 (JavaScript 렌더링 완료)
                await page.wait_for_timeout(2000)

                # 스크롤하여 lazy-load 콘텐츠 로드
                await page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight / 2)"
                )
                await page.wait_for_timeout(1000)

                # HTML 콘텐츠 가져오기
                html = await page.content()

                await browser.close()

                if not html or len(html) < 1000:
                    logger.warning("Playwright: HTML 콘텐츠 불충분")
                    return None

                logger.info(f"Playwright HTML 가져오기 성공: {len(html):,} bytes")

                # trafilatura로 본문 추출
                content = trafilatura.extract(
                    html,
                    favor_recall=True,
                    include_comments=False,
                    include_tables=True,
                )

                if not content or len(content) < 100:
                    # trafilatura 실패 시 BeautifulSoup fallback
                    logger.info(
                        "Playwright: trafilatura 불충분, BeautifulSoup 파싱 시도..."
                    )
                    soup = self.parse_html(html)
                    content = self._extract_medium_body(soup)

                if not content or len(content) < 100:
                    logger.warning("Playwright: 콘텐츠 추출 실패")
                    return None

                # 404 페이지 콘텐츠인지 확인
                if self._is_404_content(content):
                    logger.warning(
                        "Playwright: 404 페이지 콘텐츠 감지, 유효하지 않은 아티클"
                    )
                    return None

                logger.info(f"✅ Playwright 성공! ({len(content):,} 자)")

                # 메타데이터 추출
                soup = self.parse_html(html)
                og_meta = self.extract_og_meta(soup)
                meta_info = self._extract_medium_metadata(soup)

                # 제목 결정
                title = meta_info.get("title") or og_meta.get("og_title")
                if not title:
                    title_tag = soup.find("title")
                    if title_tag:
                        title = self.text_extractor.clean_text(title_tag.get_text())

                # ArticleMetadata 생성
                metadata = self._build_metadata(
                    og_meta,
                    author=meta_info.get("author"),
                    published_at=meta_info.get("date"),
                    read_time=meta_info.get("read_time"),
                    claps=meta_info.get("claps"),
                    tags=meta_info.get("tags"),
                    subtitle=meta_info.get("subtitle"),
                )

                return CrawledArticle(
                    title=title or "Medium Article",
                    content=content,
                    url=url,
                    platform=self.platform_name,
                    metadata=metadata,
                    secondary_urls=[],
                )

        except Exception as e:
            logger.error(f"Playwright extraction error: {e}")
            return None
