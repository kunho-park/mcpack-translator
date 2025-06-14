import logging
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class WhiteListLoader(BaseLoader):
    """
    FTBQuests 챕터 값을 처리하는 로더입니다.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.whitelist = (
            ("/ftbquests/quests/chapters/", "quests"),
            ("/ftbquests/quests/chapters/", "title"),
            ("/ftbquests/quests/reward_tables/", "rewards"),
            ("/ftbquests/quests/reward_tables/", "title"),
            ("/paxi/", "name"),
            ("/paxi/", "description"),
            ("/paxi/", "desc"),
            ("/paxi/", "title"),
            ("/paxi/", "subtitle"),
            ("/paxi/", "text"),
            ("/paxi/", "tooltip"),
            ("/openloader/", "name"),
            ("/openloader/", "description"),
            ("/openloader/", "desc"),
            ("/openloader/", "title"),
            ("/openloader/", "subtitle"),
            ("/openloader/", "text"),
            ("/openloader/", "tooltip"),
        )

    def can_handle(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> bool:
        """
        맞는 형식인지 확인합니다.
        """

        if "/lang/" in input_path:
            return False

        key_finded = False
        path_finded = False
        for path, whitelist_key in self.whitelist:
            if path in input_path:
                path_finded = True
                if whitelist_key == key:
                    key_finded = True

        if key_finded and path_finded:
            return False
        elif path_finded:
            return True
        else:
            return False

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        딕셔너리 값을 처리합니다.
        현재는 그대로 반환합니다.
        """
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
        return value, False
