"""
Audio Service

LangChain과 Google Generative AI를 사용한 뉴스 스크립트 생성 서비스입니다.
OpenAI TTS API를 사용한 음성 합성 기능을 포함합니다.
ADC(Application Default Credentials) 방식으로 Vertex AI 백엔드를 사용합니다.

Step 1: 콘텐츠 → 뉴스 스크립트 (3분 분량) 생성
Step 2: TTS 음성 합성 (OpenAI gpt-4o-mini-tts)
"""

import asyncio
import io
import os
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING

from google.oauth2 import service_account
from langchain_core.messages import AIMessageChunk
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger
from openai import AsyncOpenAI
from pydub import AudioSegment
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.services.prompt_loader import format_prompt
from output_schemas.audio import NewsScript

if TYPE_CHECKING:
    from app.services.storage import StorageService


# Google Cloud 프로젝트 설정
DEFAULT_PROJECT_ID = "gen-lang-client-0039052673"
DEFAULT_LOCATION = "us-central1"

# Retry 설정
MAX_RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 2  # 최소 대기 시간 (초)
RETRY_MAX_WAIT = 10  # 최대 대기 시간 (초)


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


class AudioService:
    """뉴스 스크립트 생성 서비스"""

    def __init__(
        self,
        model_name: str | None = None,
        project_id: str | None = None,
        location: str = DEFAULT_LOCATION,
        prompt_version: str = "v1",
    ):
        """
        Args:
            model_name: 사용할 Gemini 모델 이름 (None이면 settings에서 로드)
            project_id: Google Cloud 프로젝트 ID
            location: Google Cloud 리전
            prompt_version: 사용할 프롬프트 버전
        """
        # settings에서 AudioService 전용 설정 로드
        self.model_name = model_name or settings.AUDIO_SCRIPT_MODEL
        self.project_id = project_id or os.environ.get(
            "GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID
        )
        self.location = location
        self.prompt_version = prompt_version

        # Thinking 설정
        self.thinking_level = settings.AUDIO_SCRIPT_THINKING_LEVEL
        self.thinking_budget = (
            settings.AUDIO_SCRIPT_THINKING_BUDGET
            if self.thinking_level.lower() != "off"
            else 0
        )
        self.include_thoughts = settings.AUDIO_SCRIPT_INCLUDE_THOUGHTS
        self.temperature = settings.AUDIO_SCRIPT_TEMPERATURE

        # 자격 증명 및 LLM 초기화
        credentials = _get_credentials()

        # ChatGoogleGenerativeAI 사용
        # credentials 또는 project 파라미터가 있으면 자동으로 Vertex AI 백엔드 사용
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            credentials=credentials,
            project=self.project_id,
            temperature=self.temperature,
            thinking_budget=self.thinking_budget,
            include_thoughts=self.include_thoughts,
        )

        # Structured Output 적용
        self.llm_structured = self.llm.with_structured_output(NewsScript)

        # Streaming용 LLM (Thinking 기능 활성화, Plain Text 출력)
        # thinking_budget > 0 이면 AI의 추론 과정을 스트리밍으로 받을 수 있음
        # include_thoughts=True 설정이 있어야 thinking 블록이 응답에 포함됨
        self.llm_streaming = ChatGoogleGenerativeAI(
            model=self.model_name,
            credentials=credentials,
            project=self.project_id,
            temperature=self.temperature,
            thinking_budget=self.thinking_budget,
            include_thoughts=self.include_thoughts,
        )

        # ===== OpenAI TTS 설정 =====
        self.tts_model = settings.TTS_MODEL
        self.tts_voice = settings.TTS_VOICE
        self.tts_silence_padding_ms = settings.TTS_SILENCE_PADDING_MS
        self.tts_instructions = settings.TTS_INSTRUCTIONS

        # OpenAI 클라이언트 (비동기)
        # settings에서 API 키를 명시적으로 전달 (pydantic-settings가 .env에서 로드)
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        logger.info(
            f"AudioService 초기화 완료: model={self.model_name}, "
            f"project={self.project_id}, location={location}, "
            f"thinking_level={self.thinking_level}, thinking_budget={self.thinking_budget}, "
            f"temperature={self.temperature}, "
            f"tts_model={self.tts_model}, tts_voice={self.tts_voice}"
        )

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

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_retry,
        reraise=True,
    )
    async def _invoke_llm(self, prompt: str) -> NewsScript:
        """
        LLM을 호출하여 뉴스 스크립트를 생성합니다. (재시도 로직 포함)

        Args:
            prompt: 스크립트 생성 프롬프트

        Returns:
            NewsScript: 생성된 뉴스 스크립트

        Raises:
            Exception: 최대 재시도 후에도 실패 시
        """
        return await self.llm_structured.ainvoke(prompt)

    async def generate_script(
        self,
        content: str,
        original_content: str | None = None,
    ) -> NewsScript:
        """
        콘텐츠를 뉴스 스크립트로 변환합니다.

        Args:
            content: 변환할 콘텐츠 텍스트
            original_content: 원본 외부 링크 콘텐츠 (GeekNews 등, 선택)

        Returns:
            NewsScript: 뉴스 스크립트 결과 (paragraphs, title, estimated_duration_sec, total_characters)

        Raises:
            ValueError: 콘텐츠가 비어있는 경우
            Exception: LLM 호출 실패 시 (최대 3회 재시도 후)
        """
        if not content or not content.strip():
            raise ValueError("변환할 콘텐츠가 비어있습니다.")

        # 콘텐츠 병합 (original_content가 있으면)
        merged_content = self._merge_content(content, original_content)

        # 프롬프트 생성
        prompt = format_prompt(
            version=self.prompt_version,
            name="news_script",
            content=merged_content,
        )

        logger.debug(
            f"스크립트 생성 요청: 콘텐츠 길이={len(content)}자"
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
                f"스크립트 생성 완료: {len(result.paragraphs)}개 문단, "
                f"총 {result.total_characters}자, "
                f"예상 {result.estimated_duration_sec}초"
            )
            return result
        except RetryError as e:
            # 모든 재시도가 실패한 경우
            logger.error(
                f"스크립트 생성 실패 (최대 {MAX_RETRY_ATTEMPTS}회 재시도 후): {e}"
            )
            raise
        except Exception as e:
            logger.error(f"스크립트 생성 실패: {e}")
            raise

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_retry,
        reraise=True,
    )
    def _invoke_llm_sync(self, prompt: str) -> NewsScript:
        """
        LLM을 동기적으로 호출하여 뉴스 스크립트를 생성합니다. (재시도 로직 포함)
        """
        return self.llm_structured.invoke(prompt)

    def generate_script_sync(
        self,
        content: str,
        original_content: str | None = None,
    ) -> NewsScript:
        """
        콘텐츠를 동기적으로 뉴스 스크립트로 변환합니다.

        Args:
            content: 변환할 콘텐츠 텍스트
            original_content: 원본 외부 링크 콘텐츠 (GeekNews 등, 선택)

        Returns:
            NewsScript: 뉴스 스크립트 결과
        """
        if not content or not content.strip():
            raise ValueError("변환할 콘텐츠가 비어있습니다.")

        # 콘텐츠 병합 (original_content가 있으면)
        merged_content = self._merge_content(content, original_content)

        prompt = format_prompt(
            version=self.prompt_version,
            name="news_script",
            content=merged_content,
        )

        logger.debug(
            f"스크립트 생성 요청 (동기): 콘텐츠 길이={len(content)}자"
            + (
                f", 원본 콘텐츠 길이={len(original_content)}자"
                if original_content
                else ""
            )
        )

        try:
            result = self._invoke_llm_sync(prompt)
            logger.info(
                f"스크립트 생성 완료: {len(result.paragraphs)}개 문단, "
                f"총 {result.total_characters}자, "
                f"예상 {result.estimated_duration_sec}초"
            )
            return result
        except RetryError as e:
            logger.error(
                f"스크립트 생성 실패 (최대 {MAX_RETRY_ATTEMPTS}회 재시도 후): {e}"
            )
            raise
        except Exception as e:
            logger.error(f"스크립트 생성 실패: {e}")
            raise

    async def generate_script_stream(
        self,
        content: str,
        original_content: str | None = None,
    ) -> AsyncGenerator[tuple[str, str], None]:
        """
        스트리밍으로 뉴스 스크립트를 생성합니다 (Thinking 포함).

        Args:
            content: 변환할 콘텐츠 텍스트
            original_content: 원본 외부 링크 콘텐츠 (GeekNews 등, 선택)

        Yields:
            (event_type, text) 튜플
            - event_type: "thinking" | "content"
            - text: 스트리밍된 텍스트 청크
        """
        if not content or not content.strip():
            raise ValueError("변환할 콘텐츠가 비어있습니다.")

        # 콘텐츠 병합 (original_content가 있으면)
        merged_content = self._merge_content(content, original_content)

        # 스트리밍용 프롬프트 (Plain Text 출력)
        prompt = format_prompt(
            version=self.prompt_version,
            name="news_script_stream",
            content=merged_content,
        )

        logger.debug(
            f"스트리밍 스크립트 생성 요청: 콘텐츠 길이={len(content)}자"
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
            logger.error(f"스트리밍 스크립트 생성 실패: {e}")
            raise

    @staticmethod
    def parse_stream_result(full_content: str) -> NewsScript:
        """
        스트리밍된 Plain Text 결과를 NewsScript로 파싱합니다.

        예상 형식:
        ```
        [제목]
        뉴스 헤드라인 제목

        [스크립트]
        첫 번째 문단입니다.

        두 번째 문단입니다.

        세 번째 문단입니다.
        ```

        Args:
            full_content: 전체 스트리밍된 텍스트

        Returns:
            NewsScript: 파싱된 뉴스 스크립트 결과
        """
        title = ""
        paragraphs: list[str] = []

        # [제목] 파싱
        title_match = re.search(
            r"\[제목\]\s*\n(.+?)(?:\n\n|\n\[|$)", full_content, re.DOTALL
        )
        if title_match:
            title = title_match.group(1).strip()

        # [스크립트] 파싱 - 빈 줄로 구분된 문단 추출
        script_match = re.search(
            r"\[스크립트\]\s*\n([\s\S]*?)$", full_content, re.DOTALL
        )
        if script_match:
            script_text = script_match.group(1).strip()
            # 빈 줄로 문단 분리 (연속된 빈 줄도 하나로 처리)
            raw_paragraphs = re.split(r"\n\n+", script_text)
            for p in raw_paragraphs:
                p = p.strip()
                if p:
                    paragraphs.append(p)

        # 파싱 실패 시 fallback
        if not title:
            # 첫 번째 줄을 제목으로 사용
            lines = full_content.strip().split("\n")
            if lines:
                title = lines[0].strip()[:50]  # 최대 50자

        if not paragraphs:
            # 전체 내용을 하나의 문단으로 사용
            paragraphs = [full_content.strip()[:500]]

        # 총 글자 수 계산
        total_characters = sum(len(p) for p in paragraphs)

        # 예상 시간 계산 (한국어 평균 분당 300자 기준)
        estimated_duration_sec = int(total_characters / 300 * 60)

        logger.debug(
            f"스트리밍 스크립트 파싱: title='{title[:30]}...', "
            f"paragraphs={len(paragraphs)}개, total_characters={total_characters}"
        )

        return NewsScript(
            title=title,
            paragraphs=paragraphs,
            estimated_duration_sec=estimated_duration_sec,
            total_characters=total_characters,
        )

    # =========================================================================
    # TTS 음성 합성 메서드 (Step 2)
    # =========================================================================

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_retry,
        reraise=True,
    )
    async def _call_openai_tts(self, text: str) -> bytes:
        """
        단일 텍스트를 OpenAI TTS API로 음성 합성합니다.

        Args:
            text: 음성으로 변환할 텍스트

        Returns:
            MP3 오디오 바이트 데이터
        """
        async with self.openai_client.audio.speech.with_streaming_response.create(
            model=self.tts_model,
            voice=self.tts_voice,
            input=text,
            instructions=self.tts_instructions,
            response_format="mp3",
        ) as response:
            audio_bytes = await response.read()

        return audio_bytes

    def _merge_audio_chunks(
        self,
        chunks: list[bytes],
        silence_ms: int | None = None,
    ) -> tuple[bytes, float]:
        """
        오디오 청크들을 silence padding과 함께 병합합니다.

        Args:
            chunks: MP3 오디오 바이트 리스트
            silence_ms: 문단 사이 silence 길이 (ms). None이면 settings 값 사용

        Returns:
            (병합된 MP3 바이트, 전체 duration 초)
        """
        if silence_ms is None:
            silence_ms = self.tts_silence_padding_ms

        if not chunks:
            raise ValueError("병합할 오디오 청크가 없습니다.")

        # 첫 번째 청크로 시작
        combined = AudioSegment.from_mp3(io.BytesIO(chunks[0]))

        # silence 생성 (stereo, 44100Hz 기준)
        silence = AudioSegment.silent(duration=silence_ms)

        # 나머지 청크들을 silence와 함께 병합
        for chunk in chunks[1:]:
            audio_segment = AudioSegment.from_mp3(io.BytesIO(chunk))
            combined = combined + silence + audio_segment

        # MP3로 내보내기
        output_buffer = io.BytesIO()
        combined.export(output_buffer, format="mp3")
        output_bytes = output_buffer.getvalue()

        # duration 계산 (밀리초 → 초)
        duration_sec = len(combined) / 1000.0

        return output_bytes, duration_sec

    async def synthesize_speech(
        self,
        script: NewsScript,
        article_id: str,
        user_id: str,
        storage: "StorageService | None" = None,
    ) -> dict:
        """
        뉴스 스크립트를 음성으로 합성합니다.

        1. 각 문단을 OpenAI TTS API로 합성 (병렬 처리)
        2. 문단 사이에 silence padding 추가
        3. 전체 오디오 병합 후 StorageService로 저장

        Args:
            script: 합성할 뉴스 스크립트
            article_id: 아티클 ID (파일명에 사용)
            user_id: 사용자 ID (저장 경로에 사용)
            storage: StorageService 인스턴스 (None이면 get_storage_service() 사용)

        Returns:
            {
                "audio_path": str (저장된 경로),
                "duration_sec": float,
                "file_size_bytes": int,
                "paragraph_count": int,
            }

        Raises:
            ValueError: 스크립트가 비어있는 경우
            Exception: TTS API 호출 또는 파일 저장 실패 시
        """
        if not script.paragraphs:
            raise ValueError("합성할 스크립트 문단이 없습니다.")

        logger.info(
            f"TTS 합성 시작: article_id={article_id}, "
            f"문단 수={len(script.paragraphs)}, user_id={user_id}"
        )

        # 각 문단을 병렬로 TTS 합성
        tasks = [self._call_openai_tts(paragraph) for paragraph in script.paragraphs]
        audio_chunks = await asyncio.gather(*tasks)

        logger.debug(f"TTS API 호출 완료: {len(audio_chunks)}개 청크 생성")

        # 오디오 청크 병합
        merged_audio, duration_sec = self._merge_audio_chunks(list(audio_chunks))

        logger.debug(f"오디오 병합 완료: duration={duration_sec:.1f}초")

        # StorageService로 저장
        if storage is None:
            from app.services.storage import get_storage_service

            storage = get_storage_service()

        # 저장 경로
        path = f"users/{user_id}/audio/{article_id}.mp3"
        saved_path = await storage.save_bytes(
            path, merged_audio, content_type="audio/mpeg"
        )

        file_size_bytes = len(merged_audio)

        logger.info(
            f"TTS 합성 완료: {saved_path}, "
            f"duration={duration_sec:.1f}초, size={file_size_bytes / 1024:.1f}KB"
        )

        return {
            "audio_path": saved_path,
            "duration_sec": duration_sec,
            "file_size_bytes": file_size_bytes,
            "paragraph_count": len(script.paragraphs),
        }


# 싱글톤 인스턴스 (지연 초기화)
_audio_service: AudioService | None = None


def get_audio_service() -> AudioService:
    """
    AudioService 싱글톤 인스턴스를 가져옵니다.

    Returns:
        AudioService 인스턴스
    """
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService()
    return _audio_service
