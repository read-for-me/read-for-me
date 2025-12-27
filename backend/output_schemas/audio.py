"""
Audio Output Schema

뉴스 스크립트 생성 결과를 위한 Pydantic 스키마를 정의합니다.
LangChain의 with_structured_output()에서 사용됩니다.
"""

from pydantic import BaseModel, Field


class NewsScript(BaseModel):
    """뉴스 스크립트 스키마 - LLM Structured Output용"""

    paragraphs: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="문단별 스크립트 (목표: 8~12개, TTS 청킹용). 각 문단은 80~120자 권장",
    )
    title: str = Field(
        ...,
        description="뉴스 헤드라인 제목",
    )
    estimated_duration_sec: int = Field(
        ...,
        ge=30,  # 최소 30초 (유연하게 허용)
        le=600,  # 최대 10분 (유연하게 허용)
        description="예상 분량 (초). 목표: 180초 (3분)",
    )
    total_characters: int = Field(
        ...,
        ge=100,
        le=5000,
        description="총 글자 수. 목표: 900~1,050자 (3분 분량)",
    )
