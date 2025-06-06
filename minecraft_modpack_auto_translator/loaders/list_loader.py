import logging
from typing import Any, List

from .base_loader import BaseLoader
from .context import TranslationContext


class ListLoader(BaseLoader):
    """
    리스트 값을 처리하는 로더입니다.
    리스트 내 각 항목이 문자열인 경우 번역합니다.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def can_handle(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> bool:
        """
        값이 일반 리스트인지 확인합니다.
        """
        return isinstance(value, list) and all(isinstance(item, str) for item in value)

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        리스트 내 각 문자열 항목을 번역합니다.
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
            translated_list: List[str] = []

            for item in value:
                if not isinstance(item, str) or item.strip() == "":
                    translated_list.append(item if isinstance(item, str) else "")
                    continue

                # 문자열 항목에 대한 번역 수행
                processed_item = item.replace("\\n", "\n")

                state = translation_graph.invoke(
                    {
                        "text": processed_item,
                        "custom_dictionary_dict": context.custom_dictionary_dict,
                        "context": context,
                    }
                )

                translated_list.append(state["restored_text"])

            return translated_list
        except Exception as e:
            self.logger.error(f"리스트 번역 중 오류 발생: {e}")
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
        리스트 내 각 문자열 항목을 비동기적으로 번역합니다.
        """
        translation_graph = context.translation_graph

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value, True

        try:
            translated_list: List[str] = []
            has_error = False  # has_error 변수 초기화

            for item in value:
                if not isinstance(item, str) or item.strip() == "":
                    translated_list.append(item if isinstance(item, str) else "")
                    continue

                # 문자열 항목에 대한 번역 수행
                processed_item = item.replace("\\n", "\n")

                state = await translation_graph.ainvoke(
                    {
                        "text": processed_item,
                        "custom_dictionary_dict": context.custom_dictionary_dict,
                        "llm": llm,
                        "context": context,
                        "translation_key": key,
                    }
                )
                # 각 번역 후 오류 상태 업데이트
                if state.get("has_error", False):
                    has_error = True

                translated_list.append(state["restored_text"])

            return translated_list, has_error  # 최종 오류 상태 반환
        except Exception as e:
            self.logger.error(f"리스트 비동기 번역 중 오류 발생: {e}")
            return value, True
