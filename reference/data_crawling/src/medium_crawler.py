"""
Medium Crawler Module

Medium 아티클 페이지를 크롤링합니다.
BaseCrawler를 상속받아 OOP 구조를 유지하며, Medium의 복잡한 DOM 구조를 파싱합니다.

Usage:
    python medium_crawler.py https://medium.com/@shahbhat/building-a-production-grade-enterprise-ai-platform-with-vllm-a-complete-guide-from-the-trenches-cf8e7a7bdfb6
    python medium_crawler.py https://medium.com/... --output ./medium_docs
"""

import argparse
import re
import json
from typing import Optional, List, Dict

from bs4 import BeautifulSoup, Tag
from loguru import logger

from base_crawler import BaseCrawler, CrawledContent, BaseTextExtractor


class MediumTextExtractor(BaseTextExtractor):
    """
    Medium 페이지 특화 텍스트 추출기
    Medium의 불필요한 UI 요소(로그인 버튼, 앱 열기 배너 등)를 제거합니다.
    """
    REMOVE_SELECTORS = [
        "script", "style", "noscript", "iframe",
        "nav", "footer", 
        "button", 
        "[data-testid='headerSignUpButton']",
        "[data-testid='headerSignInButton']",
        ".speechify-ignore",  # 오디오 듣기 버튼 관련 텍스트
        ".grecaptcha-badge"
    ]

    def clean_medium_html(self, soup: BeautifulSoup) -> BeautifulSoup:
        """HTML에서 노이즈 요소를 제거합니다."""
        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()
        return soup


class MediumCrawler(BaseCrawler):
    """
    Medium 아티클 크롤러
    
    특징:
    - data-testid 속성을 활용한 안정적인 메타데이터 추출
    - 본문 내 코드 블록(pre), 인용구(blockquote), 리스트 보존
    - JSON-LD 데이터를 통한 보조 정보 추출
    """
    
    platform_name: str = "medium"
    # Medium 표준 URL 및 커스텀 도메인 대응을 위한 패턴 (느슨한 검사)
    URL_PATTERN: str = r"https?://.*medium\.com/.*|https?://.*" 
    
    def __init__(
        self, 
        output_dir: str = "./medium_articles", 
        timeout: int = 30,
        save_local: bool = True,
        save_gcs: bool = False
    ):
        # BaseCrawler로 옵션 전달
        super().__init__(
            output_dir=output_dir, 
            timeout=timeout,
            save_local=save_local,
            save_gcs=save_gcs
        )
        self.text_extractor = MediumTextExtractor()
        logger.info(f"Initialized MediumCrawler (Local={save_local}, GCS={save_gcs})")

    def extract(self, url: str) -> Optional[CrawledContent]:
        """URL 검증 및 콘텐츠 추출 실행"""
        # HTML 가져오기
        html = self.fetch_html(url)
        if html is None:
            return None
        
        soup = self.parse_html(html)
        
        # Medium 페이지 여부 확인 (meta 태그 등으로 2차 검증 가능)
        if not soup.select_one("meta[property='al:ios:app_name'][content='Medium']"):
            logger.warning(f"URL might not be a Medium article: {url}")

        return self._parse_content(soup, url)

    def _parse_content(self, soup: BeautifulSoup, url: str) -> Optional[CrawledContent]:
        """Medium HTML 파싱 로직"""
        try:
            # 1. 노이즈 제거
            soup = self.text_extractor.clean_medium_html(soup)

            # 2. 메타데이터 추출 (제목, 작성자, 날짜 등)
            meta_info = self._extract_metadata(soup)
            
            # 3. 본문 추출
            content_body = self._extract_article_body(soup)
            
            # 4. 최종 텍스트 조립
            full_content = []
            
            # 헤더 정보
            if meta_info.get("subtitle"):
                full_content.append(f"📝 Subtitle: {meta_info['subtitle']}\n")
            
            info_line = []
            if meta_info.get("author"): info_line.append(f"Author: {meta_info['author']}")
            if meta_info.get("date"): info_line.append(f"Date: {meta_info['date']}")
            if meta_info.get("read_time"): info_line.append(f"Read Time: {meta_info['read_time']}")
            if meta_info.get("claps"): info_line.append(f"👏 Claps: {meta_info['claps']}")
            
            if info_line:
                full_content.append(" | ".join(info_line))
                full_content.append("-" * 40 + "\n")
            
            # 본문 내용
            full_content.append(content_body)
            
            # 태그 정보
            if meta_info.get("tags"):
                full_content.append("\n" + "-" * 40)
                full_content.append(f"🏷️ Tags: {', '.join(meta_info['tags'])}")

            return CrawledContent(
                title=meta_info.get("title", "Untitled Medium Article"),
                content="\n".join(full_content),
                url=url,
                platform=self.platform_name,
                metadata=meta_info
            )

        except Exception as e:
            logger.error(f"Error parsing Medium content: {e}")
            return None

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """
        data-testid 및 OpenGraph 태그를 사용하여 메타데이터 추출
        """
        meta = {}
        
        # 제목
        title_elem = soup.select_one('[data-testid="storyTitle"]') or soup.select_one('h1.pw-post-title')
        if title_elem:
            meta["title"] = self.text_extractor.clean_text(title_elem.get_text())
        else:
            meta["title"] = soup.find("title").get_text() if soup.find("title") else ""

        # 부제목 (h2 등) - 보통 제목 바로 뒤에 위치
        subtitle_elem = soup.select_one('.pw-subtitle-paragraph')
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
            meta["read_time"] = self.text_extractor.clean_text(read_time_elem.get_text())

        # 박수(Claps) 수
        # data-testid="headerClapButton" 내부 혹은 footerClapButton 내부의 숫자 확인
        clap_elem = soup.select_one('[data-testid="headerClapButton"]') or soup.select_one('[data-testid="footerClapButton"]')
        if clap_elem:
            # 버튼 안의 텍스트에서 숫자만 추출 시도
            clap_text = clap_elem.get_text(strip=True)
            # "96" 같은 숫자만 남기기 (아이콘 텍스트 제거)
            meta["claps"] = re.sub(r'[^0-9K\.]', '', clap_text)

        # JSON-LD에서 태그나 추가 정보 추출 (선택적)
        script_json = soup.find("script", type="application/ld+json")
        if script_json:
            try:
                data = json.loads(script_json.string)
                if isinstance(data, dict):
                    # 키워드/태그 추출 시도 (schema.org 표준에 따름)
                    if "keywords" in data:
                        meta["tags"] = data["keywords"] if isinstance(data["keywords"], list) else data["keywords"].split(",")
            except json.JSONDecodeError:
                pass

        return meta

    def _extract_article_body(self, soup: BeautifulSoup) -> str:
        """
        Medium 본문 구조를 순회하며 텍스트 추출 및 포맷팅
        """
        # Medium의 본문은 보통 section 태그 안에 있음
        article_content = soup.select_one('section')
        if not article_content:
            # fallback: article 태그 전체 사용
            article_content = soup.select_one('article')
            
        if not article_content:
            return ""

        content_parts = []
        
        # 본문 내의 모든 의미 있는 태그들을 순서대로 처리
        # Medium uses: h1-h6, p, blockquote, pre, ul, ol, figure
        tags = article_content.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'blockquote', 'pre', 'ul', 'ol', 'figure'])
        
        for tag in tags:
            # 이미지 캡션 처리 (figure)
            if tag.name == 'figure':
                img = tag.find('img')
                caption = tag.find('figcaption')
                if img:
                    alt_text = img.get('alt', '')
                    src = img.get('src', '')
                    caption_text = caption.get_text(strip=True) if caption else ""
                    
                    # 이미지는 링크 형태로 표시
                    content_parts.append(f"\n[Image: {alt_text}]({src})")
                    if caption_text:
                        content_parts.append(f"  └─ <caption>: {caption_text}")
                continue

            # 코드 블록 처리 (pre)
            if tag.name == 'pre':
                code_text = tag.get_text(separator="\n", strip=True)
                content_parts.append(f"\n```\n{code_text}\n```\n")
                continue

            # 인용구 처리
            if tag.name == 'blockquote':
                quote_text = self.text_extractor.clean_text(tag.get_text())
                content_parts.append(f"\n> {quote_text}\n")
                continue

            # 리스트 처리
            if tag.name in ['ul', 'ol']:
                for li in tag.find_all('li'):
                    marker = "-" if tag.name == 'ul' else "1."
                    content_parts.append(f"{marker} {self.text_extractor.clean_text(li.get_text())}")
                content_parts.append("") # 리스트 끝에 줄바꿈
                continue

            # 헤더 처리
            if tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(tag.name[1])
                text = self.text_extractor.clean_text(tag.get_text())
                content_parts.append(f"\n{'#' * level} {text}\n")
                continue

            # 일반 문단 (p)
            text = self.text_extractor.clean_text(tag.get_text())
            if text:
                content_parts.append(text)

        return "\n".join(content_parts)


def main():
    parser = argparse.ArgumentParser(description="Medium Article Crawler")
    parser.add_argument("url", help="Target Medium Article URL")
    parser.add_argument("--output", "-o", default="medium_articles", help="Output directory")

    # GCS Flags
    parser.add_argument("--gcs", action="store_true", help="Upload to GCS")
    parser.add_argument("--no-local", action="store_true", help="Do not save locally")
    
    args = parser.parse_args()

    logger.remove()
    logger.add(lambda msg: print(msg), level="INFO")
    
    save_local = not args.no_local
    
    # 로깅 설정 (간단히)
    logger.remove()
    logger.add(lambda msg: print(msg), level="INFO")

    # BaseCrawler를 상속받았으므로 init에 인자 전달 가능
    with MediumCrawler(
        output_dir=args.output, 
        save_local=save_local, 
        save_gcs=args.gcs
    ) as crawler:
        filepath = crawler.crawl_and_save(args.url)
        if filepath:
            print(f"\n✅ Saved successfully to: {filepath}")
        else:
            print(f"\n❌ Failed to crawl.")
            
if __name__ == "__main__":
    main()