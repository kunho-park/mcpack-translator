from typing import Any, List, Mapping, Optional, Union

import g4f.models
from g4f.client import AsyncClient
from g4f.Provider.base_provider import BaseProvider
from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.llms.base import LLM
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama
from langchain_community.llms.utils import enforce_stop_tokens
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import BaseRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

MAX_TRIES = 5


class G4FLLM(LLM):
    model: Union[str, g4f.models.Model]
    provider: Optional[type[BaseProvider]] = None
    auth: Optional[Union[str, bool]] = None
    create_kwargs: Optional[dict[str, Any]] = None
    temperature: float = 0.1

    @property
    def _llm_type(self) -> str:
        return "custom"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        client = AsyncClient()
        create_kwargs = {} if self.create_kwargs is None else self.create_kwargs.copy()
        create_kwargs["model"] = self.model
        if self.provider is not None:
            create_kwargs["provider"] = self.provider
        if self.auth is not None:
            create_kwargs["auth"] = self.auth

        for i in range(MAX_TRIES):
            try:
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    **create_kwargs,
                )
                text = response.choices[0].message.content

                if stop is not None:
                    text = enforce_stop_tokens(text, stop)
                if text:
                    return text
                print(f"Empty response, trying {i + 1} of {MAX_TRIES}")
            except Exception as e:
                print(f"Error in G4FLLM._call: {e}, trying {i + 1} of {MAX_TRIES}")
        return ""

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        client = AsyncClient()
        create_kwargs = {} if self.create_kwargs is None else self.create_kwargs.copy()
        create_kwargs["model"] = self.model
        if self.provider is not None:
            create_kwargs["provider"] = self.provider
        if self.auth is not None:
            create_kwargs["auth"] = self.auth

        create_kwargs.pop("stream", None)

        for i in range(MAX_TRIES):
            try:
                response = await client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    **create_kwargs,
                )
                text = response.choices[0].message.content

                if stop is not None:
                    text = enforce_stop_tokens(text or "", stop)
                if text:
                    if run_manager:
                        await run_manager.on_llm_end(response)
                    return text
                print(f"Empty response, trying {i + 1} of {MAX_TRIES}")
            except Exception as e:
                print(f"Error in G4FLLM._acall: {e}, trying {i + 1} of {MAX_TRIES}")

        if run_manager:
            pass
        return ""

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "model": self.model,
            "provider": self.provider,
            "auth": self.auth,
            "create_kwargs": self.create_kwargs,
        }


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
        provider: 모델 제공자 (openai, google, grok, ollama, anthropic, g4f)
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
    elif provider == "g4f":
        return G4FLLM(
            model=g4f.models.gpt_4o,
        )
    else:
        raise ValueError(f"지원하지 않는 모델 제공자입니다: {provider}")
