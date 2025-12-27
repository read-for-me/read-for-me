"""
GeekNews Article Crawler

GeekNews 개별 아티클(토픽) 페이지를 크롤링합니다.
URL 형식: https://news.hada.io/topic?id=XXXXX

원본 외부 링크 크롤링 기능:
- GEEKNEWS_CRAWL_ORIGINAL=true 환경변수 설정 시 활성화
- trafilatura 라이브러리를 사용하여 원본 웹페이지의 본문 추출

Usage:
    crawler = GeekNewsCrawler()
    article = await crawler.extract("https://news.hada.io/topic?id=24268")

    # 원본 크롤링 명시적 활성화
    crawler = GeekNewsCrawler(crawl_original=True)
"""

import re

import trafilatura
from bs4 import BeautifulSoup
from loguru import logger

from app.core.config import settings
from app.services.crawlers.base import BaseCrawler
from app.services.crawlers.schemas import CrawledArticle


class GeekNewsCrawler(BaseCrawler):
    """
    GeekNews Article 크롤러

    개별 아티클(토픽) 페이지에서 다음 정보를 추출합니다:
    - 제목
    - 원본 URL (외부 링크)
    - 작성자 정보
    - 포인트 및 댓글 수
    - 본문 내용 (topic_contents)
    - 댓글 (선택, include_comments=True)
    """

    platform_name: str = "geeknews"
    URL_PATTERN: str = r"https?://(www\.)?news\.hada\.io/topic\?id=\d+"

    # GeekNews 특화 노이즈 요소 선택자
    NOISE_SELECTORS: list[str] = [
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

    def __init__(
        self,
        include_comments: bool = False,
        crawl_original: bool | None = None,
        timeout: float | None = None,
        headers: dict | None = None,
    ):
        """
        Args:
            include_comments: 댓글 포함 여부. 기본값 False
            crawl_original: 원본 외부 링크 크롤링 여부.
                           None이면 환경변수(GEEKNEWS_CRAWL_ORIGINAL) 사용.
                           명시적으로 True/False 지정 시 해당 값 사용.
            timeout: HTTP 요청 타임아웃 (초). 기본값 30초
            headers: 커스텀 HTTP 헤더
        """
        super().__init__(timeout=timeout, headers=headers)
        self.include_comments = include_comments

        # 환경변수에서 기본값 로드, 명시적 인자가 있으면 그것을 사용
        if crawl_original is None:
            self.crawl_original = settings.GEEKNEWS_CRAWL_ORIGINAL
        else:
            self.crawl_original = crawl_original

        logger.debug(
            f"GeekNewsCrawler initialized: crawl_original={self.crawl_original}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 추상 메서드 구현
    # ─────────────────────────────────────────────────────────────────────────

    def validate_url(self, url: str) -> bool:
        """
        URL이 GeekNews 아티클 URL인지 검증합니다.

        Args:
            url: 검증할 URL

        Returns:
            유효한 GeekNews URL이면 True
        """
        return bool(re.match(self.URL_PATTERN, url))

    async def extract(self, url: str) -> CrawledArticle | None:
        """
        GeekNews 아티클 URL에서 콘텐츠를 추출합니다.

        전체 크롤링 파이프라인:
        1. validate_url()로 URL 검증
        2. fetch_html()로 HTML 가져오기
        3. parse_html()로 BeautifulSoup 파싱
        4. _parse_content()로 구조화된 데이터 추출
        5. (옵션) crawl_original=True인 경우 원본 외부 링크 크롤링

        Args:
            url: 크롤링할 GeekNews 아티클 URL

        Returns:
            CrawledArticle 객체 또는 실패 시 None
        """
        # URL 유효성 검사
        if not self.validate_url(url):
            logger.error(f"Invalid GeekNews URL: {url}")
            return None

        # HTML 가져오기
        html = await self.fetch_html(url)
        if html is None:
            return None

        # HTML 파싱
        soup = self.parse_html(html)

        # 콘텐츠 추출
        article = self._parse_content(soup, url)

        if article is None:
            return None

        # 원본 외부 링크 크롤링 (옵션)
        if self.crawl_original and article.metadata.original_url:
            logger.info(f"Crawling original content: {article.metadata.original_url}")
            original_content = await self._crawl_original_content(
                article.metadata.original_url
            )

            # 새 CrawledArticle 생성 (Pydantic 모델은 불변이므로 재생성)
            article = CrawledArticle(
                title=article.title,
                content=article.content,
                url=article.url,
                platform=article.platform,
                crawled_at=article.crawled_at,
                metadata=article.metadata,
                secondary_urls=article.secondary_urls,
                original_content=original_content,
            )

        return article

    def _parse_content(self, soup: BeautifulSoup, url: str) -> CrawledArticle | None:
        """
        BeautifulSoup에서 GeekNews 아티클 데이터를 추출합니다.

        Args:
            soup: BeautifulSoup 객체
            url: 원본 URL

        Returns:
            CrawledArticle 객체 또는 실패 시 None
        """
        try:
            # 제목 추출
            title = self._extract_title(soup)
            if not title:
                logger.warning(f"Failed to extract title from {url}")
                title = "GeekNews Article"

            # 원본 링크 추출
            original_url = self._extract_original_url(soup)

            # 메타 정보 추출 (작성자, 포인트, 시간)
            meta_info = self._extract_meta_info(soup)

            # 본문 내용 추출
            main_content = self._extract_main_content(soup)

            # 댓글 추출 (옵션)
            comments = []
            if self.include_comments:
                comments = self._extract_comments(soup)

            # 전체 콘텐츠 조합
            content = self._build_content(
                original_url=original_url,
                meta_info=meta_info,
                main_content=main_content,
                comments=comments,
            )

            # OG 메타데이터 추출
            og_meta = self.extract_og_meta(soup)

            # 토픽 ID 추출
            topic_id = self._extract_topic_id(url)

            # ArticleMetadata 생성
            metadata = self._build_metadata(
                og_meta,
                original_url=original_url,
                points=meta_info.get("points"),
                author=meta_info.get("author"),
                published_at=meta_info.get("published_time"),
                comment_count=len(comments)
                if self.include_comments
                else self._get_comment_count(soup),
                topic_id=topic_id,
            )

            return CrawledArticle(
                title=title,
                content=content,
                url=url,
                platform=self.platform_name,
                metadata=metadata,
                secondary_urls=[original_url] if original_url else [],
            )

        except Exception as e:
            logger.error(f"Error parsing GeekNews article content: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Private Helper 메서드
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """
        아티클 제목을 추출합니다.

        선택자 우선순위:
        1. .topictitle h1
        2. .topictitle a.ud
        3. <title> 태그 (fallback)
        """
        # .topictitle h1
        title_elem = soup.select_one(".topictitle h1")
        if title_elem:
            return self.text_extractor.clean_text(title_elem.get_text(strip=True))

        # .topictitle a.ud
        title_link = soup.select_one(".topictitle a.ud")
        if title_link:
            return self.text_extractor.clean_text(title_link.get_text(strip=True))

        # <title> 태그 fallback
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # " | GeekNews" 접미사 제거
            return re.sub(r"\s*\|\s*GeekNews\s*$", "", title_text)

        return ""

    def _extract_original_url(self, soup: BeautifulSoup) -> str:
        """
        원본 외부 링크를 추출합니다.

        GeekNews 내부 링크는 제외합니다.
        """
        link_elem = soup.select_one(".topictitle a.ud")
        if link_elem:
            href = link_elem.get("href", "")
            # 내부 링크 제외 (/, news.hada.io)
            if href and not href.startswith("/") and "news.hada.io" not in href:
                return href
        return ""

    def _extract_meta_info(self, soup: BeautifulSoup) -> dict:
        """
        메타 정보를 추출합니다.

        추출 항목:
        - points: 포인트 (예: "42P" → "42")
        - author: 작성자
        - published_time: 게시 시간 (ISO 형식)
        - relative_time: 상대 시간 (예: "3일전")
        """
        meta_info = {}

        info_elem = soup.select_one(".topicinfo")
        if not info_elem:
            return meta_info

        info_text = info_elem.get_text(strip=True)

        # 포인트 추출 (숫자P 패턴)
        points_match = re.search(r"(\d+)P", info_text)
        if points_match:
            meta_info["points"] = points_match.group(1)

        # 작성자 추출
        author_link = info_elem.select_one("a[href*='/user']")
        if author_link:
            meta_info["author"] = author_link.get_text(strip=True)

        # 게시 시간 추출 (ISO 형식)
        time_elem = info_elem.select_one("span[title]")
        if time_elem:
            meta_info["published_time"] = time_elem.get("title", "")
        else:
            # 상대 시간 fallback
            time_match = re.search(r"(\d+[일시분초]+\s*전)", info_text)
            if time_match:
                meta_info["relative_time"] = time_match.group(1)

        return meta_info

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        본문 내용을 추출합니다.

        선택자: .topic_contents
        """
        content_elem = soup.select_one(".topic_contents")
        if not content_elem:
            return ""

        # 내부 콘텐츠 요소 찾기
        inner_content = content_elem.select_one("#topic_contents, span")
        target_elem = inner_content if inner_content else content_elem

        return self._format_content(target_elem)

    def _format_content(self, element) -> str:
        """
        콘텐츠를 마크다운 형식으로 포맷팅합니다.

        변환 규칙:
        - ul/li → bullet point (•)
        - h1-h6 → # 헤더
        - blockquote → > 인용구
        - code → `코드`
        """
        if element is None:
            return ""

        # ul/li → bullet point
        for ul in element.find_all("ul"):
            for li in ul.find_all("li"):
                if li.string:
                    li.string = f"• {li.string}"
                else:
                    li.insert(0, "• ")

        # h1-h6 → # 헤더
        for i in range(1, 7):
            for header in element.find_all(f"h{i}"):
                text = header.get_text(strip=True)
                header.string = f"\n{'#' * i} {text}\n"

        # blockquote → > 인용구
        for bq in element.find_all("blockquote"):
            text = bq.get_text(strip=True)
            bq.string = f"\n> {text}\n"

        # code → `코드`
        for code in element.find_all("code"):
            text = code.get_text(strip=True)
            code.string = f"`{text}`"

        # 텍스트 추출 및 정리
        text = element.get_text(separator="\n", strip=True)
        return self.text_extractor.clean_text(text)

    def _extract_comments(self, soup: BeautifulSoup) -> list[dict]:
        """
        댓글을 추출합니다.

        HTML 구조: <div class="comment_row" style="--depth:N"> ... </div>

        Returns:
            댓글 딕셔너리 목록 (depth, author, time, content 포함)
        """
        comments = []

        # 댓글 컨테이너 찾기
        comment_thread = soup.select_one("#comment_thread, .comment_thread")
        if comment_thread is None:
            return comments

        # 개별 댓글 행 순회
        for comment_row in comment_thread.select(".comment_row"):
            comment = {}

            # Depth 추출 (style="--depth:0")
            style = comment_row.get("style", "")
            depth_match = re.search(r"--depth:(\d+)", style)
            comment["depth"] = int(depth_match.group(1)) if depth_match else 0

            # 작성자
            author_elem = comment_row.select_one(".commentinfo a[href*='/user']")
            if author_elem:
                comment["author"] = author_elem.get_text(strip=True)

            # 시간
            time_elem = comment_row.select_one(".commentinfo a[href*='comment?id']")
            if time_elem:
                comment["time"] = time_elem.get_text(strip=True)

            # 내용 추출
            content_elem = comment_row.select_one(".comment_contents")
            if content_elem:
                raw_text = content_elem.get_text(separator="\n", strip=True)
                comment["content"] = self.text_extractor.clean_text(raw_text)

            if comment.get("content"):
                comments.append(comment)

        return comments

    def _get_comment_count(self, soup: BeautifulSoup) -> int:
        """
        댓글 수를 추출합니다.

        .topicinfo 내 "댓글 N개" 패턴에서 추출합니다.
        """
        info_elem = soup.select_one(".topicinfo")
        if not info_elem:
            return 0

        comment_link = info_elem.find("a", string=re.compile(r"댓글\s*\d+개"))
        if comment_link:
            match = re.search(r"(\d+)", comment_link.get_text())
            if match:
                return int(match.group(1))

        return 0

    def _extract_topic_id(self, url: str) -> str | None:
        """
        URL에서 토픽 ID를 추출합니다.

        예: https://news.hada.io/topic?id=24268 → "24268"
        """
        id_match = re.search(r"id=(\d+)", url)
        return id_match.group(1) if id_match else None

    def _build_content(
        self,
        original_url: str,
        meta_info: dict,
        main_content: str,
        comments: list[dict],
    ) -> str:
        """
        추출된 데이터를 하나의 콘텐츠 문자열로 조합합니다.

        메타데이터(원본 링크, 포인트, 작성자 등)는 metadata 필드에 별도 저장되므로
        여기서는 순수 본문 콘텐츠와 댓글만 포함합니다.

        Args:
            original_url: 원본 외부 링크 (사용하지 않음, metadata에 저장)
            meta_info: 메타 정보 딕셔너리 (사용하지 않음, metadata에 저장)
            main_content: 본문 텍스트
            comments: 댓글 목록

        Returns:
            조합된 콘텐츠 문자열 (본문 + 댓글)
        """
        content_parts = []

        # 본문만 포함 (메타데이터는 metadata 필드에 별도 저장됨)
        if main_content:
            content_parts.append(main_content)

        # 댓글 (include_comments=True인 경우에만)
        if comments:
            content_parts.append("")
            content_parts.append(f"## 댓글 ({len(comments)}개)")
            content_parts.append("")

            for _i, comment in enumerate(comments, 1):
                depth = comment.get("depth", 0)
                indent = "  " * depth
                marker = "↳ " if depth > 0 else ""

                author = comment.get("author", "Anonymous")
                time = comment.get("time", "")
                content = comment.get("content", "")

                # 헤더 (번호, 작성자, 시간)
                header = f"{indent}{marker}**{author}** ({time})"
                content_parts.append(header)

                # 내용 (멀티라인인 경우 들여쓰기 유지)
                content_lines = content.split("\n")
                for line in content_lines:
                    content_parts.append(f"{indent}{line}")
                content_parts.append("")

        return "\n".join(content_parts)

    # ─────────────────────────────────────────────────────────────────────────
    # 원본 외부 링크 크롤링
    # ─────────────────────────────────────────────────────────────────────────

    async def _crawl_original_content(self, original_url: str) -> str:
        """
        원본 외부 링크의 콘텐츠를 크롤링합니다.

        trafilatura 라이브러리를 사용하여 다양한 웹페이지에서
        본문 텍스트를 안정적으로 추출합니다.

        Args:
            original_url: 원본 외부 링크 URL

        Returns:
            추출된 텍스트 콘텐츠 또는 실패 시 빈 문자열
        """
        try:
            logger.info(f"Fetching original content from: {original_url}")

            # HTML 가져오기
            html = await self.fetch_html(original_url)
            if html is None:
                logger.warning(f"Failed to fetch original URL: {original_url}")
                return ""

            # trafilatura로 본문 추출
            content = trafilatura.extract(
                html,
                include_comments=False,  # 댓글 제외
                include_tables=True,  # 테이블 포함
                no_fallback=False,  # fallback 알고리즘 사용
                favor_recall=True,  # 더 많은 콘텐츠 추출 선호
            )

            if content and len(content) > 100:
                logger.info(
                    f"Successfully extracted original content "
                    f"({len(content)} chars) from: {original_url}"
                )
                return self.text_extractor.clean_text(content)

            # trafilatura 실패 시 fallback: 기본 추출
            logger.warning(
                f"trafilatura extraction insufficient, trying fallback: {original_url}"
            )
            fallback_content = self._extract_content_fallback(html)

            if fallback_content:
                logger.info(
                    f"Fallback extraction successful "
                    f"({len(fallback_content)} chars) from: {original_url}"
                )
                return fallback_content

            logger.warning(f"No content extracted from original URL: {original_url}")
            return ""

        except Exception as e:
            logger.error(f"Error crawling original content from {original_url}: {e}")
            return ""

    def _extract_content_fallback(self, html: str) -> str:
        """
        trafilatura 실패 시 사용하는 fallback 본문 추출.

        일반적인 아티클 HTML 구조에서 본문을 추출합니다.

        Args:
            html: HTML 문자열

        Returns:
            추출된 텍스트 콘텐츠
        """
        try:
            soup = self.parse_html(html)

            # 노이즈 요소 제거
            noise_selectors = [
                "script",
                "style",
                "nav",
                "header",
                "footer",
                "aside",
                ".sidebar",
                ".advertisement",
                ".ad",
                ".social-share",
                ".comments",
                ".related-posts",
                "iframe",
                ".nav",
                ".menu",
                ".navigation",
            ]
            clean_soup = self.text_extractor.remove_noise_elements(
                soup, noise_selectors
            )

            # 본문 추출 우선순위 (일반적인 아티클 구조)
            content_selectors = [
                "article",
                '[role="main"]',
                "main",
                ".post-content",
                ".article-content",
                ".entry-content",
                ".content",
                ".post-body",
                "#content",
                ".prose",  # Tailwind CSS 기반 사이트
            ]

            for selector in content_selectors:
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
