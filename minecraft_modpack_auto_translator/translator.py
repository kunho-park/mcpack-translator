from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import BaseRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


def get_translator(
    provider: str,
    api_key: str,
    model_name: str,
    api_base: Optional[str] = None,
    temperature: float = 0.1,
    rate_limiter: Optional[BaseRateLimiter] = None,
) -> BaseChatModel:
    """
    다양한 LLM 제공자를 지원하는 번역기 생성 함수

    Args:
        provider: 모델 제공자 (openai, google, grok, ollama, anthropic)
        api_key: API 키
        model_name: 모델 이름
        api_base: API 베이스 URL (기본값: None)
        temperature: 생성 온도 (기본값: 0.1)
        rate_limiter: API 요청 속도 제한기 (기본값: None)

    Returns:
        BaseChatModel: 채팅 모델 인스턴스
    """
    if isinstance(api_base, str):
        if api_base.strip() == "":
            api_base = None
    # 모델 제공자에 따라 적절한 LLM 인스턴스 생성
    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=api_base,
            temperature=temperature,
            rate_limiter=rate_limiter,
        )
    elif provider == "google":
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            rate_limiter=rate_limiter,
        )
    elif provider == "grok":
        if api_base is None:
            api_base = "https://api.grok.ai/v1"
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=api_base,
            temperature=temperature, 
            rate_limiter=rate_limiter,
        )
    elif provider == "ollama":
        if api_base is None:
            api_base = "http://localhost:11434"
        return ChatOllama(
            model=model_name,
            base_url=api_base,
            temperature=temperature,
            rate_limiter=rate_limiter,
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=model_name,
            anthropic_api_key=api_key,
            temperature=temperature,
            rate_limiter=rate_limiter,
        )
    else:
        raise ValueError(f"지원하지 않는 모델 제공자입니다: {provider}")
