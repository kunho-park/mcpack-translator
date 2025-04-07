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
        llm = context.llm

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

        def translate_value(value, translation_graph, custom_dictionary_dict, llm):
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
                        "llm": llm,
                    }
                )
                return state["restored_text"]
            elif isinstance(value, list):
                if sum(not isinstance(item, str) for item in value) == 0:
                    return translate_value(
                        "\n".join(value), translation_graph, custom_dictionary_dict, llm
                    ).split("\n")
                else:
                    return [
                        translate_value(
                            item, translation_graph, custom_dictionary_dict, llm
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
                            llm,
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
                            llm,
                        )
        return value


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
        llm = context.llm

        if not translation_graph:
            self.logger.error("번역 그래프가 제공되지 않았습니다.")
            return value

        value_dict = json.loads(value)
        state = translation_graph.invoke(
            {
                "text": value_dict["text"],
                "custom_dictionary_dict": custom_dictionary_dict,
                "llm": llm,
            }
        )
        value_dict["text"] = state["restored_text"]

        return json.dumps(value_dict, ensure_ascii=False)
