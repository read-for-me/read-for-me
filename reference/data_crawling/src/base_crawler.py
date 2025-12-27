"""
Base Crawler Module

확장 가능한 웹 크롤러의 기본 추상 클래스를 정의합니다.
다양한 웹 소스(GeekNews, GitHub, Substack, Turing-Post 등)로 확장할 수 있도록 설계되었습니다.
"""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger

from gcs_handler import GCSHandler


@dataclass
class CrawledContent:
    """크롤링된 콘텐츠를 담는 데이터 클래스"""
    
    title: str
    content: str
    url: str
    platform: str
    crawled_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "platform": self.platform,
            "crawled_at": self.crawled_at.isoformat(),
            "metadata": self.metadata
        }
    
    def to_text(self) -> str:
        """텍스트 형식으로 변환"""
        lines = [
            f"{'='*60}",
            f"Title: {self.title}",
            f"URL: {self.url}",
            f"Platform: {self.platform}",
            f"Crawled At: {self.crawled_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'='*60}",
            "",
        ]
        
        # 메타데이터 추가
        if self.metadata:
            lines.append("--- Metadata ---")
            for key, value in self.metadata.items():
                lines.append(f"{key}: {value}")
            lines.append("")
        
        lines.append("--- Content ---")
        lines.append(self.content)
        
        return "\n".join(lines)


class BaseCrawler(ABC):
    """
    모든 웹 크롤러의 기본 추상 클래스
    
    새로운 크롤러를 만들 때 이 클래스를 상속받아 구현합니다.
    """
    
    # 클래스 변수: 플랫폼 식별자
    platform_name: str = "base"
    
    # 기본 요청 헤더
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # GCS 설정
    GCS_PROJECT_ID = "gen-lang-client-0039052673"
    GCS_BUCKET_NAME = "parallel_audio_etl_data"
    
    def __init__(
        self,
        output_dir: str = "./output",
        timeout: int = 30,
        headers: Optional[dict] = None,
        save_local: bool = True,
        save_gcs: bool = False
    ):
        """
        Args:
            output_dir: 출력 파일을 저장할 디렉토리
            timeout: HTTP 요청 타임아웃 (초)
            headers: 커스텀 HTTP 헤더
        """
        self.output_dir = Path(output_dir)
        self.timeout = timeout
        self.headers = headers or self.DEFAULT_HEADERS.copy()
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.save_local = save_local
        self.save_gcs = save_gcs
        
        self.gcs_handler = None
        if self.save_gcs:
            self.gcs_handler = GCSHandler(self.GCS_PROJECT_ID, self.GCS_BUCKET_NAME)
            logger.info(f"GCS Upload Enabled: gs://{self.GCS_BUCKET_NAME}")

        if self.save_local:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Local Storage Enabled: {self.output_dir}")
    
    def fetch_html(self, url: str) -> Optional[str]:
        """
        URL에서 HTML을 가져옵니다.
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            HTML 문자열 또는 실패 시 None
        """
        try:
            logger.info(f"Fetching HTML from: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch HTML from {url}: {e}")
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
    
    @abstractmethod
    def extract(self, url: str) -> Optional[CrawledContent]:
        """
        URL에서 콘텐츠를 추출합니다.
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            CrawledContent 객체 또는 실패 시 None
        """
        pass
    
    @abstractmethod
    def _parse_content(self, soup: BeautifulSoup, url: str) -> Optional[CrawledContent]:
        """
        BeautifulSoup 객체에서 콘텐츠를 파싱합니다.
        
        Args:
            soup: BeautifulSoup 객체
            url: 원본 URL
            
        Returns:
            CrawledContent 객체 또는 실패 시 None
        """
        pass
    
    def save_to_file(
        self,
        content: "CrawledContent", 
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        크롤링된 콘텐츠를 저장합니다 (Local 및 GCS 중복 체크 포함).
        """
        if filename is None:
            safe_title = self._sanitize_filename(content.title)
            
            # 1. 고유 ID 확인 (Topic ID, Week ID 등)
            unique_id = content.metadata.get("topic_id") or content.metadata.get("week_id")
            
            if unique_id:
                # ID가 있으면 ID를 사용하여 고유성 보장 (예: geeknews_article_24460_Title.txt)
                filename = f"{content.platform}_{unique_id}_{safe_title}.txt"
            else:
                # 2. ID가 없으면 날짜(YYYYMMDD)만 사용 (하루에 한 번만 저장되도록)
                date_tag = datetime.now().strftime("%Y%m%d")
                filename = f"{content.platform}_{safe_title}_{date_tag}.txt"
        
        text_content = content.to_text()
        saved_path = None

        # 1. Local Save (중복 체크)
        if self.save_local:
            saved_path = self.output_dir / filename
            if saved_path.exists():
                logger.info(f"⏭️  Skipped local save (Duplicate): {saved_path}")
            else:
                try:
                    with open(saved_path, "w", encoding="utf-8") as f:
                        f.write(text_content)
                    logger.info(f"💾 Saved locally to: {saved_path}")
                except Exception as e:
                    logger.error(f"❌ Failed to save locally: {e}")

        # 2. GCS Upload (중복 체크)
        if self.save_gcs and self.gcs_handler:
            try:
                current_folder_name = self.output_dir.name
                gcs_path = f"{content.platform}/{current_folder_name}/{filename}"
                
                # GCS 존재 여부 확인
                if self.gcs_handler.file_exists(gcs_path):
                    logger.info(f"⏭️  Skipped GCS upload (Duplicate): gs://{self.gcs_handler.bucket_name}/{gcs_path}")
                else:
                    self.gcs_handler.upload_string(text_content, gcs_path)
            except Exception as e:
                logger.error(f"❌ GCS Upload failed logic: {e}")

        # 로컬 저장을 안하더라도(saved_path가 없어도), 논리적인 파일 경로는 호출자에게 필요할 수 있음
        if not saved_path:
             saved_path = self.output_dir / filename

        return saved_path

    def crawl_and_save(self, url: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        URL을 크롤링하고 파일로 저장합니다.
        
        Args:
            url: 크롤링할 URL
            filename: 저장할 파일명 (선택)
            
        Returns:
            저장된 파일 경로 또는 실패 시 None
        """
        content = self.extract(url)
        if content is None:
            logger.error(f"Failed to extract content from: {url}")
            return None
        
        return self.save_to_file(content, filename)
    
    @staticmethod
    def _sanitize_filename(text: str, max_length: int = 50) -> str:
        """
        파일명에 사용할 수 없는 문자를 제거합니다.
        
        Args:
            text: 원본 텍스트
            max_length: 최대 길이
            
        Returns:
            정제된 파일명
        """
        # 파일명에 사용할 수 없는 문자 제거
        sanitized = re.sub(r'[<>:"/\\|?*\n\r\t]', '', text)
        # 공백을 언더스코어로 변환
        sanitized = re.sub(r'\s+', '_', sanitized)
        # 길이 제한
        return sanitized[:max_length].strip('_')
    
    @staticmethod
    def get_domain(url: str) -> str:
        """URL에서 도메인을 추출합니다."""
        parsed = urlparse(url)
        return parsed.netloc
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()


class BaseTextExtractor:
    """HTML에서 텍스트를 추출하는 유틸리티 클래스"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        텍스트를 정리합니다.
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정리된 텍스트
        """
        if not text:
            return ""
        
        # 연속된 공백/줄바꿈 정리
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        # 각 줄의 앞뒤 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()
    
    @staticmethod
    def extract_text_from_element(element, separator: str = "\n") -> str:
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