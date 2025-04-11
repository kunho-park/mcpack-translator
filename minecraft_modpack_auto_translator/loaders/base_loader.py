from abc import ABC, abstractmethod
from typing import Any

from .context import TranslationContext


class BaseLoader(ABC):
    """
    모든 로더의 기본 추상 클래스입니다.
    로더는 특정 유형의, 또는 특정 형식의 데이터를 처리합니다.
    """

    @abstractmethod
    def can_handle(self, path: str, value: Any, context: TranslationContext) -> bool:
        """
        이 로더가 주어진 경로와 값을 처리할 수 있는지 확인합니다.

        Args:
            path: JSON 파일 내 키 경로
            value: 처리할 값
            context: 추가 컨텍스트 정보

        Returns:
            처리 가능 여부
        """
        pass

    @abstractmethod
    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        주어진 값을 처리합니다 (예: 번역).

        Args:
            path: JSON 파일 내 키 경로
            value: 처리할 값
            context: 번역 그래프, 사전 등 컨텍스트 정보

        Returns:
            처리된 값
        """
        pass

    async def aprocess(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        주어진 값을 비동기적으로 처리합니다.
        기본적으로 동기 process 메서드를 호출합니다.
        필요시 하위 클래스에서 오버라이드하여 실제 비동기 구현을 제공할 수 있습니다.

        Args:
            path: JSON 파일 내 키 경로
            value: 처리할 값
            context: 번역 그래프, 사전 등 컨텍스트 정보

        Returns:
            처리된 값
        """
        return self.process(input_path, key, value, context)
