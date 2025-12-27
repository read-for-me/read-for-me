"""
GeekNews Weekly Crawler

GeekNews Weekly 뉴스레터 페이지를 크롤링합니다.
URL 형식: https://news.hada.io/weekly/YYYYWW (예: /weekly/202546)

Usage:
    python geeknews_weekly_crawler.py https://news.hada.io/weekly/202546 --gcs
    python geeknews_weekly_crawler.py https://news.hada.io/weekly/202546 --gcs --no-local
"""

import argparse
import json
import re
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from base_crawler import CrawledContent
from geeknews_base import GeekNewsBaseCrawler


class GeekNewsWeeklyCrawler(GeekNewsBaseCrawler):
    """
    GeekNews Weekly 크롤러
    
    Weekly 뉴스레터 페이지에서 다음 정보를 추출합니다:
    - 제목 (주차 정보 포함)
    - 날짜 범위
    - 메인 설명 (desc)
    - 토픽 리스트 (topics) -> JSONL로도 저장 (Local / GCS)
    """
    
    platform_name: str = "geeknews_weekly"
    URL_PATTERN: str = r"https?://(www\.)?news\.hada\.io/weekly/\d+"
    
    def __init__(
        self, 
        output_dir: str = "./geeknews/weekly", 
        timeout: int = 30,
        save_local: bool = True,
        save_gcs: bool = False
    ):
        # 상위 클래스(GeekNewsBaseCrawler -> BaseCrawler)에 저장 설정 전달
        super().__init__(
            output_dir=output_dir, 
            timeout=timeout,
            save_local=save_local,
            save_gcs=save_gcs
        )
        logger.info(f"Initialized GeekNewsWeeklyCrawler (Local={save_local}, GCS={save_gcs})")
    
    def _parse_content(self, soup: BeautifulSoup, url: str) -> Optional[CrawledContent]:
        """
        Weekly 페이지에서 콘텐츠를 파싱합니다.
        (기존 로직과 동일)
        """
        try:
            # 제목 추출
            title = self._extract_title(soup)
            if not title:
                logger.warning("Failed to extract title")
                title = "GeekNews Weekly"
            
            # 날짜 범위 추출
            date_range = self._extract_date_range(soup)
            
            # 메인 설명 추출
            description = self._extract_description(soup)
            
            # 토픽 리스트 추출
            topics = self._extract_topics(soup)
            
            # 전체 콘텐츠 조합 (텍스트 파일용)
            content_parts = []
            
            if date_range:
                content_parts.append(f"📅 {date_range}\n")
            
            if description:
                content_parts.append("📝 Description")
                content_parts.append("-" * 40)
                content_parts.append(description)
                content_parts.append("")
            
            if topics:
                content_parts.append("📋 Topics")
                content_parts.append("-" * 40)
                for i, topic in enumerate(topics, 1):
                    content_parts.append(f"\n[{i}] {topic.get('title', 'No Title')}")
                    if topic.get('url'):
                        content_parts.append(f"    🔗 {topic['url']}")
                    if topic.get('description'):
                        content_parts.append(f"    {topic['description']}")
            
            content = "\n".join(content_parts)
            
            # 메타데이터 추출
            metadata = self._extract_og_meta(soup)
            metadata["date_range"] = date_range
            metadata["topic_count"] = len(topics)
            metadata["raw_topics"] = topics
            
            # 주차 번호 추출
            week_match = re.search(r'/weekly/(\d+)', url)
            if week_match:
                metadata["week_id"] = week_match.group(1)
            
            return CrawledContent(
                title=title,
                content=content,
                url=url,
                platform=self.platform_name,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error parsing weekly content: {e}")
            return None

    def crawl_and_save(self, url: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        URL을 크롤링하고 저장합니다 (Text + JSONL).
        Local 및 GCS 저장 여부는 초기화 시 설정된 값을 따릅니다.
        """
        # 1. 크롤링 수행
        content = self.extract(url)
        if content is None:
            logger.error(f"Failed to extract content from: {url}")
            return None
        
        # 2. 동적 디렉토리 경로 계산 (YYYY_MM_WeekNN)
        date_range = content.metadata.get("date_range", "")
        week_id = content.metadata.get("week_id", "")
        
        folder_name = "unknown_week"
        date_match = re.search(r'(\d{4})-(\d{2})', date_range)
        if date_match and week_id:
            year, month = date_match.groups()
            week_num = week_id[-2:] 
            folder_name = f"{year}_{month}_Week{week_num}"
        elif week_id:
            folder_name = f"Week_{week_id}"
            
        # 3. 임시로 output_dir 변경 (BaseCrawler가 이 경로를 사용하여 저장함)
        original_output_dir = self.output_dir
        self.output_dir = self.output_dir / folder_name
        
        # 로컬 저장을 위해 디렉토리 생성 (Local 옵션이 켜져있을 때만)
        if self.save_local:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 4. 메인 텍스트 파일 저장 (BaseCrawler의 로직 위임: Local + GCS)
            # save_to_file 내부에서 self.save_local, self.save_gcs 체크함
            saved_path = self.save_to_file(content, filename)
            
            # 파일명 결정 (saved_path가 없으면-로컬저장X- 직접 생성)
            if saved_path:
                base_filename = saved_path.stem
            else:
                if filename:
                    base_filename = Path(filename).stem
                else:
                    safe_title = self._sanitize_filename(content.title)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    base_filename = f"{content.platform}_{safe_title}_{timestamp}"

            # 5. JSONL 파일 추가 저장 (Local + GCS)
            if content.metadata.get("raw_topics"):
                self._process_topics_jsonl(
                    topics=content.metadata["raw_topics"], 
                    base_filename=base_filename,
                    folder_name=folder_name  # GCS 경로 구성을 위해 필요
                )
                
            return saved_path
        finally:
            # 디렉토리 복구
            self.output_dir = original_output_dir

    def _process_topics_jsonl(self, topics: List[dict], base_filename: str, folder_name: str):
        """
        토픽 리스트를 JSONL 포맷으로 변환하여 저장(Local) 및 업로드(GCS)합니다.
        BaseCrawler는 텍스트 파일만 처리하므로, JSONL 같은 파생 파일은 여기서 직접 처리해야 합니다.
        """
        # 1. JSONL 컨텐츠 생성
        jsonl_lines = []
        for topic in topics:
            entry = {
                "url": topic.get("url", ""),
                "headline": topic.get("title", ""),
                "type": "article"
            }
            if entry["url"] and entry["headline"]:
                jsonl_lines.append(json.dumps(entry, ensure_ascii=False))
        
        if not jsonl_lines:
            return

        jsonl_content = "\n".join(jsonl_lines)
        jsonl_filename = f"{base_filename}.jsonl"

        # 2. Local 저장
        if self.save_local:
            local_path = self.output_dir / jsonl_filename
            if local_path.exists():
                logger.info(f"⏭️  Skipped JSONL local save (Duplicate): {local_path}")
            else:
                try:
                    with open(local_path, "w", encoding="utf-8") as f:
                        f.write(jsonl_content)
                    logger.info(f"💾 Saved JSONL locally: {local_path}")
                except Exception as e:
                    logger.error(f"❌ Failed to save JSONL locally: {e}")

        # 3. GCS 업로드
        if self.save_gcs and self.gcs_handler:
            try:
                # GCS 경로: geeknews_weekly/YYYY_MM_WeekNN/filename.jsonl
                # BaseCrawler 구조에 맞추기 위해 output_dir 구조 반영
                # self.output_dir.name은 현재 동적으로 변경된 상태임 (folder_name)
                
                # 경로 구성: platform_name / dynamic_folder / filename
                # (BaseCrawler 구현 방식에 따라 조정 가능, 여기서는 명시적 경로 사용)
                gcs_path = f"{self.platform_name}/{folder_name}/{jsonl_filename}"

                if self.gcs_handler.file_exists(gcs_path):
                    logger.info(f"⏭️  Skipped JSONL GCS upload (Duplicate): gs://{self.gcs_handler.bucket_name}/{gcs_path}")
                else:
                    self.gcs_handler.upload_string(jsonl_content, gcs_path)
                
            except Exception as e:
                logger.error(f"❌ Failed to upload JSONL to GCS: {e}")

    def _extract_title(self, soup: BeautifulSoup) -> str:
        title_elem = soup.select_one(".weekly-container h2")
        if title_elem:
            return self.text_extractor.clean_text(title_elem.get_text(strip=True))
        title_tag = soup.find("title")
        if title_tag:
            return self.text_extractor.clean_text(title_tag.get_text(strip=True))
        return ""
    
    def _extract_date_range(self, soup: BeautifulSoup) -> str:
        date_elem = soup.select_one(".date.center")
        if date_elem:
            return self.text_extractor.clean_text(date_elem.get_text(strip=True))
        return ""
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        desc_elem = soup.select_one(".desc")
        if desc_elem:
            for elem in desc_elem.select("hr, .date"):
                elem.decompose()
            return self.text_extractor.clean_text(desc_elem.get_text(separator="\n", strip=True))
        return ""
    
    def _extract_topics(self, soup: BeautifulSoup) -> list[dict]:
        topics = []
        topics_elem = soup.select_one(".topics")
        if topics_elem is None:
            return topics
        
        for li in topics_elem.select("li"):
            topic = {}
            link = li.select_one("a.link")
            if not link:
                link = li.select_one("a[href]")
            
            if link:
                topic["title"] = link.get_text(strip=True)
                href = link.get("href", "")
                if href:
                    if not href.startswith("http"):
                        topic["url"] = f"{self.BASE_URL}{href}"
                    else:
                        topic["url"] = href
            
            content_elem = li.select_one(".content")
            if content_elem:
                topic["description"] = self.text_extractor.clean_text(content_elem.get_text(strip=True))
            else:
                p_elem = li.select_one("p")
                if p_elem:
                    topic["description"] = self.text_extractor.clean_text(p_elem.get_text(strip=True))
            
            if topic.get("title") and topic.get("url"):
                topics.append(topic)
        return topics


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="GeekNews Weekly 크롤러",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("url", help="크롤링할 GeekNews Weekly URL")
    parser.add_argument("--output", "-o", default="geeknews/weekly", help="출력 디렉토리 (기본값: ./geeknews/weekly)")
    parser.add_argument("--filename", "-f", default=None, help="저장할 파일명")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 로그 출력")
    
    # GCS 및 저장 옵션
    parser.add_argument("--gcs", action="store_true", help="Google Cloud Storage 업로드 활성화")
    parser.add_argument("--no-local", action="store_true", help="로컬 저장 비활성화")
    
    args = parser.parse_args()
    
    if not args.verbose:
        logger.remove()
        logger.add(lambda msg: print(msg), level="INFO")
    
    save_local = not args.no_local
    
    with GeekNewsWeeklyCrawler(
        output_dir=args.output,
        save_local=save_local,
        save_gcs=args.gcs
    ) as crawler:
        result = crawler.crawl_and_save(args.url, filename=args.filename)
        
        if result or args.gcs: # 로컬 저장이 없어도 GCS가 성공하면 성공으로 간주
            print(f"\n✅ Crawling completed for: {args.url}")
        else:
            print(f"\n❌ Failed to crawl: {args.url}")
            exit(1)


if __name__ == "__main__":
    main()