import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class GlobalPacksOriginLoader(BaseLoader):
    """
    GlobalPacks 의 Origin들  값을 처리하는 로더입니다.
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
        return "/global_packs/required_data/" in input_path

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        딕셔너리 값을 처리합니다.
        현재는 그대로 반환합니다.
        """
        pass

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
        """
        translation_graph = context.translation_graph
        custom_dictionary_dict = context.custom_dictionary_dict

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

        if key not in self.json_key_white_list:
            return value, False

        if isinstance(value, str):
            state = await translation_graph.ainvoke(
                {
                    "text": value,
                    "custom_dictionary_dict": custom_dictionary_dict,
                    "llm": llm,
                    "context": context,
                    "translation_key": key,
                }
            )
            return state["restored_text"], state["has_error"]
        else:
            return value, False
