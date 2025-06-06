import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class PatchouliBooksLoader(BaseLoader):
    """
    Patchouli 책 값을 처리하는 로더입니다.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.json_key_white_list = [
            "pages",
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
        return (
            isinstance(value, list)
            and "pages" == key
            and "/patchouli_books/" in input_path
            and isinstance(value[0], dict)
        )

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        딕셔너리 값을 처리합니다.
        현재는 그대로 반환합니다.
        """
        translation_graph = context.translation_graph
        custom_dictionary_dict = context.custom_dictionary_dict

        # 동기 메서드는 일반적으로 사용되지 않기 때문에 경고만 로깅합니다
        self.logger.warning(
            "동기 메서드는 LLM이 없어 번역이 제대로 수행되지 않을 수 있습니다."
        )

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

        for page in value:
            if isinstance(page, dict):
                for k in page.keys():
                    if k in self.json_key_white_list:
                        state = translation_graph.invoke(
                            {
                                "text": page[k],
                                "custom_dictionary_dict": custom_dictionary_dict,
                                "context": context,
                            }
                        )
                        page[k] = state["restored_text"]
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
        """
        translation_graph = context.translation_graph
        custom_dictionary_dict = context.custom_dictionary_dict

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value, False

        state = {"has_error": False}

        for page in value:
            if isinstance(page, dict):
                for k in page.keys():
                    if k in self.json_key_white_list:
                        state = await translation_graph.ainvoke(
                            {
                                "text": page[k],
                                "custom_dictionary_dict": custom_dictionary_dict,
                                "llm": llm,
                                "context": context,
                                "translation_key": k,
                            }
                        )
                        page[k] = state["restored_text"]
        return value, state["has_error"]
