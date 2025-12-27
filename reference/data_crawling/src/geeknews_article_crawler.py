"""
GeekNews Article Crawler

GeekNews 개별 아티클(토픽) 페이지를 크롤링합니다.
URL 형식: https://news.hada.io/topic?id=XXXXX (예: /topic?id=24268)

Usage:
    python geeknews_article_crawler.py https://news.hada.io/topic?id=24268
    python geeknews_article_crawler.py https://news.hada.io/topic?id=24268 --output ./my_output
"""

import re
import json
import argparse
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger

from base_crawler import CrawledContent
from geeknews_base import GeekNewsBaseCrawler


class GeekNewsArticleCrawler(GeekNewsBaseCrawler):
    """
    GeekNews Article 크롤러
    
    개별 아티클(토픽) 페이지에서 다음 정보를 추출합니다:
    - 제목
    - 원본 URL (외부 링크)
    - 작성자 정보
    - 포인트 및 댓글 수
    - 본문 내용 (topic_contents)
    - 댓글 (comment_contents) 및 대댓글 구조 포함
    """
    
    platform_name: str = "geeknews_article"
    URL_PATTERN: str = r"https?://(www\.)?news\.hada\.io/topic\?id=\d+"
    
    def __init__(
        self,
        output_dir: str = "./geeknews/articles",
        timeout: int = 30,
        include_comments: bool = True,
        save_local: bool = True,
        save_gcs: bool = False
    ):
        # 상위 클래스 초기화 (BaseCrawler가 저장 옵션을 처리함)
        super().__init__(
            output_dir=output_dir, 
            timeout=timeout,
            save_local=save_local,
            save_gcs=save_gcs
        )
        self.include_comments = include_comments
        logger.info(f"Initialized GeekNewsArticleCrawler (Comments={include_comments}, Local={save_local}, GCS={save_gcs})")
    
    def _parse_content(self, soup: BeautifulSoup, url: str) -> Optional[CrawledContent]:
        """
        Article 페이지에서 콘텐츠를 파싱합니다.
        """
        try:
            # 제목 추출
            title = self._extract_title(soup)
            if not title:
                logger.warning("Failed to extract title")
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
            content_parts = []
            
            # 원본 링크
            if original_url:
                content_parts.append(f"🔗 Original: {original_url}")
                content_parts.append("")
            
            # 메타 정보
            if meta_info:
                meta_str = " | ".join([f"{k}: {v}" for k, v in meta_info.items() if v])
                content_parts.append(f"📊 {meta_str}")
                content_parts.append("")
            
            # 본문
            if main_content:
                content_parts.append("📝 Content")
                content_parts.append("-" * 40)
                content_parts.append(main_content)
            
            # 댓글 [보완된 출력 로직]
            if comments:
                content_parts.append("")
                content_parts.append(f"💬 Comments ({len(comments)})")
                content_parts.append("-" * 40)
                for i, comment in enumerate(comments, 1):
                    # Depth에 따른 들여쓰기 처리
                    depth = comment.get('depth', 0)
                    indent = "    " * depth
                    marker = "└─ " if depth > 0 else ""
                    
                    author = comment.get('author', 'Anonymous')
                    time = comment.get('time', '')
                    content = comment.get('content', '')
                    
                    # 헤더 (번호, 작성자, 시간)
                    header = f"{indent}[{i}] {marker}{author} ({time})"
                    content_parts.append(f"\n{header}")
                    
                    # 내용 (멀티라인인 경우 들여쓰기 유지)
                    content_lines = content.split('\n')
                    for line in content_lines:
                        content_parts.append(f"{indent}    {line}")
            
            content = "\n".join(content_parts)
            
            # 메타데이터 구성
            metadata = self._extract_og_meta(soup)
            metadata.update(meta_info)
            metadata["original_url"] = original_url
            metadata["comment_count"] = len(comments) if self.include_comments else self._get_comment_count(soup)
            
            # 토픽 ID 추출
            id_match = re.search(r'id=(\d+)', url)
            if id_match:
                metadata["topic_id"] = id_match.group(1)
            
            return CrawledContent(
                title=title,
                content=content,
                url=url,
                platform=self.platform_name,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error parsing article content: {e}")
            return None
    
    def crawl_and_save(self, url: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        URL을 크롤링하고 날짜별 디렉토리에 저장합니다.
        GCS 업로드 시에도 이 구조를 반영하기 위해 output_dir을 임시 변경합니다.
        """
        content = self.extract(url)
        if content is None:
            logger.error(f"Failed to extract content from: {url}")
            return None
        
        # 1. 날짜 기반 폴더명 계산
        pub_time = content.metadata.get("published_time", "")
        folder_name = "unknown_date"
        
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', pub_time)
        if match:
            folder_name = f"{match.group(1)}_{match.group(2)}_{match.group(3)}"
        else:
            folder_name = datetime.now().strftime("%Y_%m_%d")
            
        # 2. 경로 임시 변경 (BaseCrawler가 이 경로를 참조하여 저장)
        original_output_dir = self.output_dir
        self.output_dir = self.output_dir / folder_name
        
        # 3. 로컬 저장소 생성 (Local 옵션이 켜진 경우만)
        if self.save_local:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 4. 저장 및 업로드 위임 (BaseCrawler)
            # GCS 업로드 시 BaseCrawler 구현에 따라 'geeknews_article/YYYY_MM_DD/filename.txt' 형태가 될 수 있음
            # (BaseCrawler가 output_dir 구조를 어떻게 GCS key로 매핑하느냐에 따라 다름)
            return self.save_to_file(content, filename)
        finally:
            self.output_dir = original_output_dir

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """아티클 제목을 추출합니다."""
        title_elem = soup.select_one(".topictitle h1")
        if title_elem:
            return self.text_extractor.clean_text(title_elem.get_text(strip=True))
        
        title_link = soup.select_one(".topictitle a.ud")
        if title_link:
            return self.text_extractor.clean_text(title_link.get_text(strip=True))
        
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            return re.sub(r'\s*\|\s*GeekNews\s*$', '', title_text)
        return ""
    
    def _extract_original_url(self, soup: BeautifulSoup) -> str:
        """원본 외부 링크를 추출합니다."""
        link_elem = soup.select_one(".topictitle a.ud")
        if link_elem:
            href = link_elem.get("href", "")
            if href and not href.startswith("/") and "news.hada.io" not in href:
                return href
        return ""
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> dict:
        """메타 정보(작성자, 포인트, 시간)를 추출합니다."""
        meta_info = {}
        info_elem = soup.select_one(".topicinfo")
        if info_elem:
            info_text = info_elem.get_text(strip=True)
            
            points_match = re.search(r'(\d+)P', info_text)
            if points_match:
                meta_info["points"] = points_match.group(1)
            
            author_link = info_elem.select_one("a[href*='/user']")
            if author_link:
                meta_info["author"] = author_link.get_text(strip=True)
            
            time_elem = info_elem.select_one("span[title]")
            if time_elem:
                meta_info["published_time"] = time_elem.get("title", "")
            else:
                time_match = re.search(r'(\d+[일시분초]+전)', info_text)
                if time_match:
                    meta_info["relative_time"] = time_match.group(1)
        return meta_info
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """본문 내용을 추출합니다."""
        content_elem = soup.select_one(".topic_contents")
        if content_elem:
            inner_content = content_elem.select_one("#topic_contents, span")
            if inner_content:
                return self._format_content(inner_content)
            return self._format_content(content_elem)
        return ""
    
    def _format_content(self, element) -> str:
        """콘텐츠를 포맷팅합니다."""
        if element is None:
            return ""
        
        for ul in element.find_all("ul"):
            for li in ul.find_all("li"):
                if li.string:
                    li.string = f"• {li.string}"
                else:
                    li.insert(0, "• ")
        
        for i in range(1, 7):
            for header in element.find_all(f"h{i}"):
                text = header.get_text(strip=True)
                header.string = f"\n{'#' * i} {text}\n"
        
        for link in element.find_all("a"):
            text = link.get_text(strip=True)
            if text:
                link.string = f"{text}"
        
        for bq in element.find_all("blockquote"):
            text = bq.get_text(strip=True)
            bq.string = f"\n> {text}\n"
        
        for code in element.find_all("code"):
            text = code.get_text(strip=True)
            code.string = f"`{text}`"
        
        text = element.get_text(separator="\n", strip=True)
        return self.text_extractor.clean_text(text)
    
    def _extract_comments(self, soup: BeautifulSoup) -> list[dict]:
        """
        댓글을 추출합니다.
        HTML 구조: <div class="comment_row" ...> ... <span class="comment_contents">
        """
        comments = []
        
        # 댓글 컨테이너 찾기
        comment_thread = soup.select_one("#comment_thread, .comment_thread")
        if comment_thread is None:
            return comments
        
        # 개별 댓글 행 순회
        for comment_row in comment_thread.select(".comment_row"):
            comment = {}
            
            # [보완] Depth 추출 (style="--depth:0")
            style = comment_row.get('style', '')
            depth_match = re.search(r'--depth:(\d+)', style)
            comment['depth'] = int(depth_match.group(1)) if depth_match else 0
            
            # 작성자
            author_elem = comment_row.select_one(".commentinfo a[href*='/user']")
            if author_elem:
                comment["author"] = author_elem.get_text(strip=True)
            
            # 시간
            time_elem = comment_row.select_one(".commentinfo a[href*='comment?id']")
            if time_elem:
                comment["time"] = time_elem.get_text(strip=True)
            
            # [보완] 내용 추출 강화 (comment_contents 클래스 타겟팅)
            # .commentTD > span.comment_contents 구조
            content_elem = comment_row.select_one(".comment_contents")
            if content_elem:
                # p 태그 등의 줄바꿈을 보존하기 위해 separator='\n' 사용
                raw_text = content_elem.get_text(separator="\n", strip=True)
                comment["content"] = self.text_extractor.clean_text(raw_text)
            
            if comment.get("content"):
                comments.append(comment)
        
        return comments
    
    def _get_comment_count(self, soup: BeautifulSoup) -> int:
        """댓글 수를 추출합니다."""
        info_elem = soup.select_one(".topicinfo")
        if info_elem:
            comment_link = info_elem.find("a", string=re.compile(r'댓글 \d+개'))
            if comment_link:
                match = re.search(r'(\d+)', comment_link.get_text())
                if match:
                    return int(match.group(1))
        return 0


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="GeekNews Article 크롤러",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("url", help="크롤링할 GeekNews Article URL")
    parser.add_argument("--output", "-o", default="geeknews/articles", help="출력 디렉토리 (기본값: ./geeknews/articles)")
    parser.add_argument("--filename", "-f", default=None, help="저장할 파일명")
    parser.add_argument("--comments", "-c", action="store_true", default=True, help="댓글 포함")
    parser.add_argument("--no-comments", dest="comments", action="store_false", help="댓글 제외")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 로그 출력")

    # GCS Flags
    parser.add_argument("--gcs", action="store_true", help="Upload to GCS")
    parser.add_argument("--no-local", action="store_true", help="Do not save locally")
    
    args = parser.parse_args()
    
    if not args.verbose:
        logger.remove()
        logger.add(lambda msg: print(msg), level="INFO")
    
    save_local = not args.no_local
    
    # BaseCrawler를 상속받았으므로 init에 인자 전달 가능
    with GeekNewsArticleCrawler(
        output_dir=args.output, 
        save_local=save_local, 
        save_gcs=args.gcs,
        include_comments=args.comments
    ) as crawler:
        filepath = crawler.crawl_and_save(args.url, filename=args.filename)
        
        if filepath:
            print(f"\n✅ Successfully saved to: {filepath}")
        else:
            print(f"\n❌ Failed to crawl: {args.url}")
            exit(1)


if __name__ == "__main__":
    main()