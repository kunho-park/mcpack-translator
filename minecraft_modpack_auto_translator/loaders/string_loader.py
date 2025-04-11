import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class StringLoader(BaseLoader):
    """
    문자열 값을 처리하는 로더입니다.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def can_handle(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> bool:
        """
        문자열 값인지 확인합니다.
        """
        return isinstance(value, str) and value.strip() != ""

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        문자열을 번역합니다.
        """
        translation_graph = context.translation_graph
        llm = context.llm

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

        try:
            # 개행 문자 처리
            processed_value = value.replace("\\n", "\n")

            # 컨텍스트 객체를 상태에 전달
            state = translation_graph.invoke(
                {
                    "text": processed_value,
                    "custom_dictionary_dict": context.custom_dictionary_dict,
                    "llm": llm,
                    "context": context,
                }
            )

            return state["restored_text"]
        except Exception as e:
            self.logger.error(f"문자열 번역 중 오류 발생: {e}")
            return value

    async def aprocess(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        문자열을 비동기적으로 번역합니다.
        """
        translation_graph = context.translation_graph
        llm = context.llm

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

        try:
            # 개행 문자 처리
            processed_value = value.replace("\\n", "\n")

            # 컨텍스트 객체를 상태에 전달 (비동기 호출)
            state = await translation_graph.ainvoke(
                {
                    "text": processed_value,
                    "custom_dictionary_dict": context.custom_dictionary_dict,
                    "llm": llm,
                    "context": context,
                }
            )

            return state["restored_text"]
        except Exception as e:
            self.logger.error(f"문자열 비동기 번역 중 오류 발생: {e}")
            return value