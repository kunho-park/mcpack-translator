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

        # 동기 메서드는 일반적으로 사용되지 않기 때문에 경고만 로깅합니다
        self.logger.warning(
            "동기 메서드는 LLM이 없어 번역이 제대로 수행되지 않을 수 있습니다."
        )

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
                    "context": context,
                }
            )

            return state["restored_text"]
        except Exception as e:
            self.logger.error(f"문자열 번역 중 오류 발생: {e}")
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
        문자열을 비동기적으로 번역합니다.
        """
        translation_graph = context.translation_graph

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

        try:
            # 개행 문자 처리
            processed_value = value.replace("\\n", "\n")

            # LLM이 명시적으로 전달되지 않았으면 인자를 통해 제공된 것 사용
            if not llm:
                self.logger.warning(
                    "LLM이 전달되지 않았습니다. 외부에서 전달 받은 LLM 파라미터를 사용합니다."
                )

            # 컨텍스트 객체를 상태에 전달 (비동기 호출)
            state = await translation_graph.ainvoke(
                {
                    "text": processed_value,
                    "custom_dictionary_dict": context.custom_dictionary_dict,
                    "llm": llm,  # llm을 직접 state에 전달
                    "context": context,
                    "translation_key": key,
                }
            )

            return state["restored_text"], state["has_error"]
        except Exception as e:
            self.logger.error(f"문자열 번역 중 오류 발생: {e}")
            return value, True
