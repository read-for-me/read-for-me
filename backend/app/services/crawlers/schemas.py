"""
Crawler Data Schemas

크롤링 관련 Pydantic 데이터 모델을 정의합니다.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class CrawlRequest(BaseModel):
    """크롤링 요청 스키마"""
    
    url: HttpUrl = Field(..., description="크롤링할 URL")


class ArticleMetadata(BaseModel):
    """아티클 메타데이터 스키마"""
    
    # Open Graph 태그
    og_title: Optional[str] = Field(None, description="OG 제목")
    og_description: Optional[str] = Field(None, description="OG 설명")
    og_image: Optional[str] = Field(None, description="OG 이미지 URL")
    og_url: Optional[str] = Field(None, description="OG URL")
    
    # 작성자 및 게시 정보
    author: Optional[str] = Field(None, description="작성자")
    published_at: Optional[str] = Field(None, description="게시일")
    
    # 플랫폼별 확장 필드
    original_url: Optional[str] = Field(None, description="원본 외부 링크 (GeekNews)")
    points: Optional[str] = Field(None, description="포인트 (GeekNews)")
    comment_count: Optional[int] = Field(None, description="댓글 수")
    read_time: Optional[str] = Field(None, description="읽는 시간 (Medium)")
    claps: Optional[str] = Field(None, description="박수 수 (Medium)")
    tags: Optional[list[str]] = Field(None, description="태그 목록")
    topic_id: Optional[str] = Field(None, description="토픽 ID (GeekNews)")
    subtitle: Optional[str] = Field(None, description="부제목 (Medium)")

    class Config:
        extra = "allow"  # 추가 필드 허용


class CrawledArticle(BaseModel):
    """크롤링 원본 결과 스키마"""
    
    title: str = Field(..., description="아티클 제목")
    content: str = Field(..., description="원본 텍스트 콘텐츠")
    url: str = Field(..., description="크롤링한 URL")
    platform: str = Field(..., description="플랫폼 식별자 (geeknews, medium)")
    crawled_at: datetime = Field(default_factory=datetime.now, description="크롤링 시각")
    metadata: ArticleMetadata = Field(default_factory=ArticleMetadata, description="메타데이터")
    secondary_urls: list[str] = Field(default_factory=list, description="2차 URL 목록 (추후 확장용)")
    
    # 원본 외부 링크의 크롤링된 콘텐츠 (GeekNews 등)
    # GEEKNEWS_CRAWL_ORIGINAL=true일 때 채워짐, 아니면 빈 문자열
    original_content: str = Field(default="", description="원본 외부 링크의 크롤링된 콘텐츠")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CleanedArticle(BaseModel):
    """ETL 후 정제된 결과 스키마 - API 응답용"""
    
    title: str = Field(..., description="아티클 제목")
    cleaned_content: str = Field(..., description="정제된 텍스트 콘텐츠")
    preview_text: str = Field(..., description="미리보기 텍스트 (앞 300자)")
    url: str = Field(..., description="원본 URL")
    platform: str = Field(..., description="플랫폼 식별자")
    crawled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: ArticleMetadata = Field(..., description="메타데이터")
    
    # 원본 외부 링크의 정제된 콘텐츠 (GeekNews 등)
    original_content: str = Field(default="", description="원본 외부 링크의 정제된 콘텐츠")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @classmethod
    def from_crawled(cls, crawled: CrawledArticle) -> "CleanedArticle":
        """CrawledArticle에서 CleanedArticle 생성"""
        # 순환 import 방지를 위해 지연 import
        from app.services.crawlers.base import BaseTextExtractor
        cleaned = BaseTextExtractor.clean_text(crawled.content)
        
        # 원본 콘텐츠도 정제 (있는 경우)
        original_cleaned = ""
        if crawled.original_content:
            original_cleaned = BaseTextExtractor.clean_text(crawled.original_content)
        
        # 미리보기 텍스트 생성 (앞 300자)
        preview = crawled.content[:300].strip()
        if len(crawled.content) > 300:
            preview += "..."
        
        return cls(
            title=crawled.title,
            cleaned_content=cleaned,
            preview_text=preview,
            url=crawled.url,
            platform=crawled.platform,
            crawled_at=crawled.crawled_at,
            metadata=crawled.metadata,
            original_content=original_cleaned,
        )
