"""
Prompt Loader

마크다운 파일에서 프롬프트 템플릿을 로드하는 유틸리티입니다.
버전 관리 및 A/B 테스트가 용이하도록 프롬프트를 파일로 분리합니다.
"""

from functools import lru_cache
from pathlib import Path

from loguru import logger

# 프롬프트 디렉토리 기본 경로 (backend/prompts/)
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


class PromptLoader:
    """프롬프트 파일 로더"""

    def __init__(self, base_dir: Path | None = None):
        """
        Args:
            base_dir: 프롬프트 파일이 위치한 기본 디렉토리.
                      None이면 기본값 (backend/prompts/) 사용.
        """
        self.base_dir = base_dir or PROMPTS_DIR

    def load(self, version: str, name: str) -> str:
        """
        프롬프트 파일을 로드합니다.

        Args:
            version: 프롬프트 버전 (예: "v1", "v2")
            name: 프롬프트 이름 (예: "summary", "audio_script")

        Returns:
            프롬프트 템플릿 문자열

        Raises:
            FileNotFoundError: 프롬프트 파일이 없을 경우
        """
        file_path = self.base_dir / version / f"{name}.md"

        if not file_path.exists():
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        logger.debug(f"프롬프트 로드 완료: {file_path}")
        return content


@lru_cache(maxsize=32)
def get_prompt(version: str, name: str) -> str:
    """
    캐싱된 프롬프트를 가져옵니다.

    Args:
        version: 프롬프트 버전 (예: "v1")
        name: 프롬프트 이름 (예: "summary")

    Returns:
        프롬프트 템플릿 문자열
    """
    loader = PromptLoader()
    return loader.load(version, name)


def format_prompt(version: str, name: str, **kwargs) -> str:
    """
    프롬프트를 로드하고 변수를 대입합니다.

    Args:
        version: 프롬프트 버전
        name: 프롬프트 이름
        **kwargs: 프롬프트에 대입할 변수들

    Returns:
        변수가 대입된 프롬프트 문자열
    """
    template = get_prompt(version, name)
    return template.format(**kwargs)
