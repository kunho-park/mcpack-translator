import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class PuffishSkillsLoader(BaseLoader):
    """
    Puffish Skills 값을 처리하는 로더입니다.
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

        self.file_white_list = [
            "definitions.json",
            "category.json",
        ]

    def can_handle(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> bool:
        """
        맞는 형식인지지 확인합니다.
        """
        return "/puffish_skills/categories/" in input_path

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
                                "translation_key": k,
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
            return value

        if not any(file in input_path for file in self.file_white_list):
            return value, False

        async def _translate_recursive(current_key: str, current_value: Any):
            """값을 타입과 키 화이트리스트에 따라 재귀적으로 번역합니다."""
            if isinstance(current_value, dict):
                processed_dict = {}
                aggregate_error = False
                for k, v in current_value.items():
                    # 중첩된 값을 재귀적으로 처리
                    translated_v, error_v = await _translate_recursive(k, v)
                    processed_dict[k] = translated_v
                    aggregate_error = aggregate_error or error_v
                return processed_dict, aggregate_error
            elif isinstance(current_value, str) and current_key in self.json_key_white_list:
                # 키가 화이트리스트에 있는 경우 문자열 값 번역
                try:
                    state = await translation_graph.ainvoke(
                        {
                            "text": current_value,
                            "custom_dictionary_dict": custom_dictionary_dict,
                            "llm": llm,
                            "context": context,
                            "translation_key": current_key,
                        }
                    )
                    # state에 예상 키가 포함되어 있는지 확인하고, 없으면 기본값 제공
                    restored_text = state.get("restored_text", current_value) # 키가 없으면 원본 반환
                    has_error = state.get("has_error", False) # 키가 없으면 False 반환
                    return restored_text, has_error
                except Exception as e:
                    self.logger.error(f"키 '{current_key}' 번역 중 오류 발생: {e}")
                    # 예외 발생 시 원본 값과 오류 상태 반환
                    return current_value, True
            else:
                # 딕셔너리나 화이트리스트에 없는 문자열이 아닌 값은 그대로 반환
                return current_value, False

        # 재귀 함수 초기 호출
        processed_value, has_error = await _translate_recursive(key, value)
        return processed_value, has_error
