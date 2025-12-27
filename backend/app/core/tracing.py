"""
Phoenix LLMOps Tracing 초기화 모듈

Arize Phoenix를 사용하여 LangChain 기반 LLM 호출을 트레이싱합니다.
"""

from loguru import logger

from app.core.config import settings


def init_tracing() -> bool:
    """
    Phoenix 트레이싱을 초기화합니다.
    
    Returns:
        bool: 초기화 성공 여부
    """
    if not settings.PHOENIX_ENABLED:
        logger.info("Phoenix 트레이싱이 비활성화되어 있습니다 (PHOENIX_ENABLED=False)")
        return False
    
    try:
        from phoenix.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor
        
        # Phoenix tracer provider 등록
        tracer_provider = register(
            project_name=settings.PHOENIX_PROJECT_NAME,
            endpoint=settings.PHOENIX_COLLECTOR_ENDPOINT,
        )
        
        # LangChain instrumentation 활성화
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        
        logger.info(
            f"Phoenix 트레이싱 초기화 완료 "
            f"(project: {settings.PHOENIX_PROJECT_NAME}, "
            f"endpoint: {settings.PHOENIX_COLLECTOR_ENDPOINT})"
        )
        return True
        
    except ImportError as e:
        logger.warning(
            f"Phoenix 트레이싱 초기화 실패 - 의존성 누락: {e}. "
            "트레이싱 없이 계속 진행합니다."
        )
        return False
    except Exception as e:
        logger.warning(
            f"Phoenix 트레이싱 초기화 실패: {e}. "
            "트레이싱 없이 계속 진행합니다."
        )
        return False

