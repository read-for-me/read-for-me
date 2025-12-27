"""
Summary Output Schema

요약 결과를 위한 Pydantic 스키마를 정의합니다.
LangChain의 with_structured_output()에서 사용됩니다.
"""

from pydantic import BaseModel, Field


class SummaryResult(BaseModel):
    """요약 결과 스키마 - LLM Structured Output용"""

    bullet_points: list[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="핵심 포인트 요약 (3-5개의 불릿 포인트)",
    )
    main_topic: str = Field(
        ...,
        description="글의 주요 주제를 한 줄로 요약",
    )

