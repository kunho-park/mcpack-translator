import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class DictLoader(BaseLoader):
    """
    딕셔너리 값을 처리하는 로더입니다.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.json_key_white_list = [
            "text",
            "title",
            "subtitle",
            "description",
            "name",
        ]

    def can_handle(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> bool:
        """
        맞는 형식인지지 확인합니다.
        """
        # JSON파일 내에서 dict 형식인 값을 확인합니다.
        return isinstance(value, dict)

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        딕셔너리 값을 처리합니다.
        현재는 그대로 반환합니다.
        """
        translation_graph = context.translation_graph

        # 동기 메서드는 일반적으로 사용되지 않기 때문에 경고만 로깅합니다
        self.logger.warning(
            "동기 메서드는 LLM이 없어 번역이 제대로 수행되지 않을 수 있습니다."
        )

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

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
        return value, False
