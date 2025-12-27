import json

from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str
    VERSION: str
    API_V1_STR: str

    # CORS 설정: 콤마로 구분된 문자열이나 리스트 모두 처리 가능하도록 검증
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    # GeekNews 원본 외부 링크 크롤링 설정
    # True: 원본 웹페이지 콘텐츠도 함께 크롤링
    # False: GeekNews 아티클만 크롤링
    GEEKNEWS_CRAWL_ORIGINAL: bool = False

    # Gemini Thinking 설정 (SummaryService용)
    # Thinking 레벨: "low", "medium", "high" 또는 비활성화 시 "off"
    GEMINI_THINKING_LEVEL: str = "low"
    # Thinking 토큰 예산
    GEMINI_THINKING_BUDGET: int = 2048

    # ===== AudioService (뉴스 스크립트 생성) 전용 설정 =====
    AUDIO_SCRIPT_MODEL: str = "gemini-2.5-flash"
    AUDIO_SCRIPT_THINKING_LEVEL: str = "low"
    AUDIO_SCRIPT_THINKING_BUDGET: int = 2048
    AUDIO_SCRIPT_INCLUDE_THOUGHTS: bool = False
    AUDIO_SCRIPT_TEMPERATURE: float = 0.5  # 대본 생성은 약간의 창의성 허용

    # ===== OpenAI TTS (음성 합성) 설정 =====
    OPENAI_API_KEY: str = ""  # OpenAI API 키 (openai SDK가 자동으로 사용)
    TTS_MODEL: str = "gpt-4o-mini-tts"
    TTS_VOICE: str = "marin"  # marin, cedar 권장 (최고 품질)
    TTS_SILENCE_PADDING_MS: int = 500  # 문단 사이 silence 길이 (ms)
    TTS_INSTRUCTIONS: str = "차분하고 전문적인 한국어 뉴스 아나운서 톤으로 읽어주세요. 명확한 발음과 적절한 속도로 진행합니다."

    # ===== Apidog 설정 (CI/CD 연동용) =====
    APIDOG_API_KEY: str = ""  # Apidog API 키
    APIDOG_PROJECT_ID: str = ""  # Apidog 프로젝트 ID

    # ===== Phoenix LLMOps 설정 =====
    PHOENIX_COLLECTOR_ENDPOINT: str = "http://localhost:6006/v1/traces"
    PHOENIX_PROJECT_NAME: str = "read-for-me"
    PHOENIX_ENABLED: bool = True

    # ===== Storage 설정 =====
    # STORAGE_BACKEND: "local" (로컬 파일시스템) | "gcs" (Google Cloud Storage)
    STORAGE_BACKEND: str = "local"
    # GCS 버킷 이름 (STORAGE_BACKEND=gcs 시 필수)
    GCS_BUCKET_NAME: str = "read-for-me-data"
    # GCS 프로젝트 ID
    GCS_PROJECT_ID: str = "gen-lang-client-0039052673"
    # GCS Signed URL 만료 시간 (분)
    GCS_SIGNED_URL_EXPIRY_MINUTES: int = 60

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str):
            # JSON 배열 형태인 경우 파싱
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # 콤마로 구분된 문자열인 경우
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        raise ValueError(v)

    # .env 파일 위치 지정 (현재 파일 기준 상위 디렉토리 탐색 등)
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )


settings = Settings()
