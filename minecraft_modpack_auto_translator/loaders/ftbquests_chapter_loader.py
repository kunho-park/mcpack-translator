import json
import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class FTBQuestsChapterQuestsLoader(BaseLoader):
    """
    FTBQuests 챕터 값을 처리하는 로더입니다.
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
        return (
            isinstance(value, list)
            and "/ftbquests/quests/chapters/" in input_path
            and "quests" == key
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

        def translate_value(value, translation_graph, custom_dictionary_dict, context):
            """
            값을 재귀적으로 번역하는 함수입니다.
            문자열, 리스트, 딕셔너리를 처리합니다.
            """
            if isinstance(value, str):
                if value == "":
                    return value
                state = translation_graph.invoke(
                    {
                        "text": value,
                        "custom_dictionary_dict": custom_dictionary_dict,
                        "context": context,
                    }
                )
                return state["restored_text"]
            elif isinstance(value, list):
                if sum(not isinstance(item, str) for item in value) == 0:
                    return translate_value(
                        "\n".join(value),
                        translation_graph,
                        custom_dictionary_dict,
                        context,
                    ).split("\n")
                else:
                    return [
                        translate_value(
                            item,
                            translation_graph,
                            custom_dictionary_dict,
                            context,
                        )
                        for item in value
                    ]
            elif isinstance(value, dict):
                for k in value.keys():
                    if k in self.json_key_white_list:
                        value[k] = translate_value(
                            value[k],
                            translation_graph,
                            custom_dictionary_dict,
                            context,
                        )
                return value
            else:
                return value

        for quest in value:
            if isinstance(quest, dict):
                for k in quest.keys():
                    if k in self.json_key_white_list:
                        quest[k] = translate_value(
                            quest[k],
                            translation_graph,
                            custom_dictionary_dict,
                            context,
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
        """
        translation_graph = context.translation_graph
        custom_dictionary_dict = context.custom_dictionary_dict

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

        async def translate_value_async(
            value, translation_graph, custom_dictionary_dict, llm, context
        ):
            """
            값을 재귀적으로 비동기 번역하는 함수입니다.
            문자열, 리스트, 딕셔너리를 처리합니다.
            """
            if isinstance(value, str):
                if value == "":
                    return value
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
            elif isinstance(value, list):
                if sum(not isinstance(item, str) for item in value) == 0:
                    translated, has_error = await translate_value_async(
                        "\n".join(value),
                        translation_graph,
                        custom_dictionary_dict,
                        llm,
                        context,
                    )
                    return translated.split("\n"), has_error
                else:
                    results = []
                    for item in value:
                        translated_item, has_error = await translate_value_async(
                            item,
                            translation_graph,
                            custom_dictionary_dict,
                            llm,
                            context,
                        )
                        results.append(translated_item)
                    return results, has_error
            elif isinstance(value, dict):
                for k in value.keys():
                    if k in self.json_key_white_list:
                        value[k], has_error = await translate_value_async(
                            value[k],
                            translation_graph,
                            custom_dictionary_dict,
                            llm,
                            context,
                        )
                return value, has_error
            else:
                return value, False

        has_error_total = False
        for quest in value:
            if isinstance(quest, dict):
                for k in quest.keys():
                    if k in self.json_key_white_list:
                        quest[k], has_error = await translate_value_async(
                            quest[k],
                            translation_graph,
                            custom_dictionary_dict,
                            llm,
                            context,
                        )
                        has_error_total = has_error_total or has_error
        return value, has_error_total


class FTBQuestsChapterTitleLoader(BaseLoader):
    """
    FTBQuests 챕터 값을 처리하는 로더입니다.
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
        return (
            isinstance(value, str)
            and "/ftbquests/quests/chapters/" in input_path
            and "title" == key
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

        value_dict = json.loads(value)
        state = translation_graph.invoke(
            {
                "text": value_dict["text"],
                "custom_dictionary_dict": custom_dictionary_dict,
                "context": context,
            }
        )
        value_dict["text"] = state["restored_text"]

        return json.dumps(value_dict, ensure_ascii=False)

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
            return value, True
        try:
            value_dict = json.loads(value)
        except json.JSONDecodeError:
            value_dict = value

        if isinstance(value_dict, dict):
            state = await translation_graph.ainvoke(
                {
                    "text": value_dict["text"],
                    "custom_dictionary_dict": custom_dictionary_dict,
                    "llm": llm,
                    "context": context,
                    "translation_key": key,
                }
            )
            value_dict["text"] = state["restored_text"]
            return json.dumps(value_dict), state["has_error"]
        else:
            state = await translation_graph.ainvoke(
                {
                    "text": value_dict,
                    "custom_dictionary_dict": custom_dictionary_dict,
                    "llm": llm,
                    "context": context,
                    "translation_key": key,
                }
            )
            return state["restored_text"], state["has_error"]
