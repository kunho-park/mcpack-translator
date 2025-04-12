import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class DictLoader(BaseLoader):
    """
    딕셔너리 값을 처리하는 로더입니다.
    현재는 경고만 출력하고 원본 값을 반환합니다.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def can_handle(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> bool:
        """
        딕셔너리 값인지 확인합니다.
        """
        return isinstance(value, dict)

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        딕셔너리 값을 처리합니다.
        현재는 그대로 반환합니다.
        """
        self.logger.info(
            f"이 형식의 딕셔너리 번역은 현재 지원되지 않습니다. ({input_path})"
        )
        return value

    async def aprocess(
        self,
        input_path: str,
        key: str,
        value: Any,
        context: TranslationContext,
        llm=None,
    ) -> Any:
        """
        딕셔너리 값을 비동기적으로 처리합니다.
        현재는 그대로 반환합니다.
        """
        self.logger.info(
            f"이 형식의 딕셔너리 번역은 현재 지원되지 않습니다. (비동기 처리: {input_path})"
        )
        return value
