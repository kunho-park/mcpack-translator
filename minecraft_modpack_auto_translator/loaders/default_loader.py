import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class DefaultLoader(BaseLoader):
    """
    다른 로더가 처리하지 않는 값들을 처리하는 기본 로더입니다.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def can_handle(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> bool:
        """
        모든 값을 처리할 수 있습니다 (가장 낮은 우선순위).
        """
        return True

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        그대로 반환합니다.
        """
        self.logger.debug(f"기본 로더가 처리: {input_path} = {value}")
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
        비동기적으로 그대로 반환합니다.
        """
        self.logger.debug(f"비동기 기본 로더가 처리: {input_path} = {value}")
        return value
