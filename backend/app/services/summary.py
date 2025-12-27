"""
Summary Service

LangChain과 Google Generative AI를 사용한 요약 서비스입니다.
ADC(Application Default Credentials) 방식으로 Vertex AI 백엔드를 사용합니다.

백엔드 자동 선택 규칙 (langchain-google-genai):
- credentials 파라미터 제공 → Vertex AI 사용
- project 파라미터 제공 → Vertex AI 사용
- GOOGLE_GENAI_USE_VERTEXAI=true → Vertex AI 사용
- 그 외 → Gemini Developer API 사용
"""

import os
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from google.oauth2 import service_account
from langchain_core.messages import AIMessageChunk
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.services.prompt_loader import format_prompt
from output_schemas.summary import SummaryResult

# Google Cloud 프로젝트 설정
DEFAULT_PROJECT_ID = "gen-lang-client-0039052673"
DEFAULT_LOCATION = "us-central1"
DEFAULT_MODEL = "gemini-2.5-flash"

# Retry 설정
MAX_RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 2  # 최소 대기 시간 (초)
RETRY_MAX_WAIT = 10  # 최대 대기 시간 (초)

# Thinking 설정 (기본값, settings에서 오버라이드됨)
DEFAULT_THINKING_BUDGET = 1024  # Thinking 토큰 예산 기본값


def _get_credentials() -> service_account.Credentials | None:
    """
    서비스 계정 자격 증명을 가져옵니다.

    환경변수 GOOGLE_APPLICATION_CREDENTIALS가 설정되어 있으면 해당 파일에서,
    없으면 기본 위치(~/readforme-key.json)에서 자격 증명을 로드합니다.

    Returns:
        service_account.Credentials 또는 None (ADC 사용 시)
    """
    # 1. 환경변수에서 키 파일 경로 확인
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    # 2. 환경변수가 없으면 기본 경로 사용
    if not credentials_path:
        default_key_path = Path.home() / "readforme-key.json"
        if default_key_path.exists():
            credentials_path = str(default_key_path)
            # 환경변수에도 설정 (다른 Google 라이브러리용)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            logger.info(f"기본 키 파일 사용: {credentials_path}")

    # 3. 키 파일이 있으면 자격 증명 생성
    if credentials_path and Path(credentials_path).exists():
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return credentials

    # 4. 키 파일이 없으면 None 반환 (ADC 자동 감지 사용)
    logger.warning(
        "서비스 계정 키 파일을 찾을 수 없습니다. ADC 자동 감지를 시도합니다."
    )
    return None


def _log_retry(retry_state) -> None:
    """재시도 전 로깅을 수행합니다."""
    exception = retry_state.outcome.exception()
    attempt = retry_state.attempt_number
    logger.warning(
        f"LLM API 호출 실패: {type(exception).__name__}: {exception}, "
        f"{attempt}번째 재시도 중..."
    )


class SummaryService:
    """콘텐츠 요약 서비스"""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        project_id: str | None = None,
        location: str = DEFAULT_LOCATION,
        prompt_version: str = "v1",
        thinking_budget: int | None = None,
    ):
        """
        Args:
            model_name: 사용할 Gemini 모델 이름
            project_id: Google Cloud 프로젝트 ID
            location: Google Cloud 리전
            prompt_version: 사용할 프롬프트 버전
            thinking_budget: Thinking 토큰 예산 (스트리밍 시 사용). None이면 settings에서 로드
        """
        self.model_name = model_name
        self.project_id = project_id or os.environ.get(
            "GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID
        )
        self.location = location
        self.prompt_version = prompt_version

        # Thinking 설정: settings에서 로드 (파라미터로 오버라이드 가능)
        self.thinking_level = settings.GEMINI_THINKING_LEVEL
        if thinking_budget is not None:
            self.thinking_budget = thinking_budget
        elif self.thinking_level.lower() == "off":
            self.thinking_budget = 0  # Thinking 비활성화
        else:
            self.thinking_budget = settings.GEMINI_THINKING_BUDGET

        # 자격 증명 및 LLM 초기화
        credentials = _get_credentials()

        # ChatGoogleGenerativeAI 사용
        # credentials 또는 project 파라미터가 있으면 자동으로 Vertex AI 백엔드 사용
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            credentials=credentials,
            project=self.project_id,
            temperature=0.3,  # 요약은 창의성보다 정확성
        )

        # Structured Output 적용
        self.llm_structured = self.llm.with_structured_output(SummaryResult)

        # Streaming용 LLM (Thinking 기능 활성화)
        # thinking_budget > 0 이면 AI의 추론 과정을 스트리밍으로 받을 수 있음
        # include_thoughts=True 설정이 있어야 thinking 블록이 응답에 포함됨
        self.llm_streaming = ChatGoogleGenerativeAI(
            model=model_name,
            credentials=credentials,
            project=self.project_id,
            temperature=0.3,
            thinking_budget=self.thinking_budget,  # Thinking 토큰 예산
            include_thoughts=True,  # Thinking 블록 포함 (필수!)
        )

        logger.info(
            f"SummaryService 초기화 완료: model={model_name}, "
            f"project={self.project_id}, location={location}, "
            f"thinking_level={self.thinking_level}, thinking_budget={self.thinking_budget}"
        )

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_retry,
        reraise=True,
    )
    async def _invoke_llm(self, prompt: str) -> SummaryResult:
        """
        LLM을 호출하여 요약을 생성합니다. (재시도 로직 포함)

        Args:
            prompt: 요약 프롬프트

        Returns:
            SummaryResult: 요약 결과

        Raises:
            Exception: 최대 재시도 후에도 실패 시
        """
        return await self.llm_structured.ainvoke(prompt)

    def _merge_content(
        self,
        content: str,
        original_content: str | None = None,
    ) -> str:
        """
        GeekNews 요약 콘텐츠와 원본 아티클 콘텐츠를 병합합니다.

        original_content가 있으면 두 소스를 구분하여 병합하고,
        없으면 기존 content만 반환합니다.

        Args:
            content: 기본 콘텐츠 (GeekNews 웹페이지 본문)
            original_content: 원본 외부 링크 콘텐츠 (선택)

        Returns:
            병합된 콘텐츠 문자열
        """
        if not original_content or not original_content.strip():
            return content

        # 두 소스를 구분하여 병합
        merged = f"""## GeekNews 요약/코멘트

{content.strip()}

## 원본 아티클

{original_content.strip()}"""

        return merged

    async def summarize(
        self,
        content: str,
        original_content: str | None = None,
    ) -> SummaryResult:
        """
        콘텐츠를 요약합니다.

        Args:
            content: 요약할 콘텐츠 텍스트
            original_content: 원본 외부 링크 콘텐츠 (GeekNews 등, 선택)

        Returns:
            SummaryResult: 요약 결과 (bullet_points, main_topic)

        Raises:
            ValueError: 콘텐츠가 비어있는 경우
            Exception: LLM 호출 실패 시 (최대 3회 재시도 후)
        """
        if not content or not content.strip():
            raise ValueError("요약할 콘텐츠가 비어있습니다.")

        # 콘텐츠 병합 (original_content가 있으면)
        merged_content = self._merge_content(content, original_content)

        # 프롬프트 생성
        prompt = format_prompt(
            version=self.prompt_version,
            name="summary",
            content=merged_content,
        )

        logger.debug(
            f"요약 요청: 콘텐츠 길이={len(content)}자"
            + (
                f", 원본 콘텐츠 길이={len(original_content)}자"
                if original_content
                else ""
            )
        )

        # LLM 호출 (비동기, 재시도 로직 포함)
        try:
            result = await self._invoke_llm(prompt)
            logger.info(
                f"요약 완료: {len(result.bullet_points)}개 포인트, "
                f"주제={result.main_topic[:30]}..."
            )
            return result
        except RetryError as e:
            # 모든 재시도가 실패한 경우
            logger.error(f"요약 실패 (최대 {MAX_RETRY_ATTEMPTS}회 재시도 후): {e}")
            raise
        except Exception as e:
            logger.error(f"요약 실패: {e}")
            raise

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_retry,
        reraise=True,
    )
    def _invoke_llm_sync(self, prompt: str) -> SummaryResult:
        """
        LLM을 동기적으로 호출하여 요약을 생성합니다. (재시도 로직 포함)
        """
        return self.llm_structured.invoke(prompt)

    def summarize_sync(
        self,
        content: str,
        original_content: str | None = None,
    ) -> SummaryResult:
        """
        콘텐츠를 동기적으로 요약합니다.

        Args:
            content: 요약할 콘텐츠 텍스트
            original_content: 원본 외부 링크 콘텐츠 (GeekNews 등, 선택)

        Returns:
            SummaryResult: 요약 결과
        """
        if not content or not content.strip():
            raise ValueError("요약할 콘텐츠가 비어있습니다.")

        # 콘텐츠 병합 (original_content가 있으면)
        merged_content = self._merge_content(content, original_content)

        prompt = format_prompt(
            version=self.prompt_version,
            name="summary",
            content=merged_content,
        )

        logger.debug(
            f"요약 요청 (동기): 콘텐츠 길이={len(content)}자"
            + (
                f", 원본 콘텐츠 길이={len(original_content)}자"
                if original_content
                else ""
            )
        )

        try:
            result = self._invoke_llm_sync(prompt)
            logger.info(
                f"요약 완료: {len(result.bullet_points)}개 포인트, "
                f"주제={result.main_topic[:30]}..."
            )
            return result
        except RetryError as e:
            logger.error(f"요약 실패 (최대 {MAX_RETRY_ATTEMPTS}회 재시도 후): {e}")
            raise
        except Exception as e:
            logger.error(f"요약 실패: {e}")
            raise

    async def summarize_stream(
        self,
        content: str,
        original_content: str | None = None,
    ) -> AsyncGenerator[tuple[str, str], None]:
        """
        스트리밍으로 요약을 생성합니다 (Thinking 포함).

        Args:
            content: 요약할 콘텐츠 텍스트
            original_content: 원본 외부 링크 콘텐츠 (GeekNews 등, 선택)

        Yields:
            (event_type, text) 튜플
            - event_type: "thinking" | "content"
            - text: 스트리밍된 텍스트 청크
        """
        if not content or not content.strip():
            raise ValueError("요약할 콘텐츠가 비어있습니다.")

        # 콘텐츠 병합 (original_content가 있으면)
        merged_content = self._merge_content(content, original_content)

        # 스트리밍용 프롬프트 (Plain Text 출력)
        prompt = format_prompt(
            version=self.prompt_version,
            name="summary_stream",
            content=merged_content,
        )

        logger.debug(
            f"스트리밍 요약 요청: 콘텐츠 길이={len(content)}자"
            + (
                f", 원본 콘텐츠 길이={len(original_content)}자"
                if original_content
                else ""
            )
        )

        try:
            async for chunk in self.llm_streaming.astream(prompt):
                if not isinstance(chunk, AIMessageChunk):
                    continue

                # content가 list인 경우 (thinking + text 블록)
                if isinstance(chunk.content, list):
                    for block in chunk.content:
                        if isinstance(block, dict):
                            block_type = block.get("type", "")
                            # Thinking 블록
                            if block_type == "thinking":
                                thinking_text = block.get("thinking", "")
                                if thinking_text:
                                    yield ("thinking", thinking_text)
                            # Reasoning 블록 (output_version에 따라 다름)
                            elif block_type == "reasoning":
                                reasoning_text = block.get("reasoning", "")
                                if reasoning_text:
                                    yield ("thinking", reasoning_text)
                            # Text 블록
                            elif block_type == "text":
                                text = block.get("text", "")
                                if text:
                                    yield ("content", text)
                        elif isinstance(block, str) and block:
                            yield ("content", block)
                # content가 문자열인 경우
                elif isinstance(chunk.content, str) and chunk.content:
                    yield ("content", chunk.content)

        except Exception as e:
            logger.error(f"스트리밍 요약 실패: {e}")
            raise

    @staticmethod
    def parse_stream_result(full_content: str) -> SummaryResult:
        """
        스트리밍된 Plain Text 결과를 SummaryResult로 파싱합니다.

        예상 형식:
        ```
        [주제]
        주제 내용

        [요약]
        • 첫 번째 포인트
        • 두 번째 포인트
        • 세 번째 포인트
        ```

        Args:
            full_content: 전체 스트리밍된 텍스트

        Returns:
            SummaryResult: 파싱된 요약 결과
        """
        main_topic = ""
        bullet_points: list[str] = []

        # [주제] 파싱
        topic_match = re.search(
            r"\[주제\]\s*\n(.+?)(?:\n\n|\n\[|$)", full_content, re.DOTALL
        )
        if topic_match:
            main_topic = topic_match.group(1).strip()

        # [요약] 파싱 - bullet points 추출
        summary_match = re.search(r"\[요약\]\s*\n(.+?)$", full_content, re.DOTALL)
        if summary_match:
            summary_text = summary_match.group(1).strip()
            # '•' 또는 '-' 또는 '*'로 시작하는 줄 추출
            lines = summary_text.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                    # 불릿 마커 제거
                    point = re.sub(r"^[•\-\*]\s*", "", line).strip()
                    if point:
                        bullet_points.append(point)

        # 파싱 실패 시 fallback
        if not main_topic:
            # 첫 번째 줄을 주제로 사용
            lines = full_content.strip().split("\n")
            if lines:
                main_topic = lines[0].strip()

        if not bullet_points:
            # 전체 내용을 하나의 포인트로 사용
            bullet_points = [full_content.strip()[:500]]

        logger.debug(
            f"스트리밍 결과 파싱: main_topic='{main_topic[:30]}...', "
            f"bullet_points={len(bullet_points)}개"
        )

        return SummaryResult(
            main_topic=main_topic,
            bullet_points=bullet_points,
        )


# 싱글톤 인스턴스 (지연 초기화)
_summary_service: SummaryService | None = None


def get_summary_service() -> SummaryService:
    """
    SummaryService 싱글톤 인스턴스를 가져옵니다.

    Returns:
        SummaryService 인스턴스
    """
    global _summary_service
    if _summary_service is None:
        _summary_service = SummaryService()
    return _summary_service
