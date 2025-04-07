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
        )

    def can_handle(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> bool:
        """
        맞는 형식인지 확인합니다.
        """
        for path, whitelist_key in self.whitelist:
            if path in input_path and key == whitelist_key:
                return False
        return True

    def process(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        딕셔너리 값을 처리합니다.
        현재는 그대로 반환합니다.
        """
        return value
