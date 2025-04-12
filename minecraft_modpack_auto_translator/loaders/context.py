import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# 전역 공유 상태
_GLOBAL_DICTIONARY = {}
_GLOBAL_DICTIONARY_LOWERCASE = {}
_GLOBAL_LOCK = asyncio.Lock()


class TranslationContext:
    """번역 컨텍스트 클래스"""

    def __init__(
        self, translation_graph, custom_dictionary_dict=None, llm=None, registry=None
    ):
        self.translation_graph = translation_graph
        self.custom_dictionary_dict = custom_dictionary_dict or {}
        self.llm = llm
        self.registry = registry

        # 번역 컨텍스트가 생성될 때 공유 사전 초기화
        self.initialize_dictionaries()

    def get(self, key: str, default: Any = None) -> Any:
        """속성 값을 가져옵니다."""
        return getattr(self, key, default)

    def initialize_dictionaries(self) -> None:
        """공유 사전을 초기화합니다."""
        global _GLOBAL_DICTIONARY, _GLOBAL_DICTIONARY_LOWERCASE

        # 전역 사전이 비어있고 커스텀 사전이 있으면 초기화
        if not _GLOBAL_DICTIONARY and self.custom_dictionary_dict:
            _GLOBAL_DICTIONARY = self.custom_dictionary_dict.copy()
            _GLOBAL_DICTIONARY_LOWERCASE = {
                k.lower(): k for k in self.custom_dictionary_dict.keys()
            }

    async def async_add_to_dictionary(self, en_value: str, ko_value: str) -> bool:
        """사전에 새 항목을 비동기적으로 추가합니다."""
        async with _GLOBAL_LOCK:
            return self._add_to_dictionary_unsafe(en_value, ko_value)

    def add_to_dictionary(self, en_value: str, ko_value: str) -> bool:
        """사전에 새 항목을 추가합니다."""
        return self._add_to_dictionary_unsafe(en_value, ko_value)

    def _add_to_dictionary_unsafe(self, en_value: str, ko_value: str) -> bool:
        """락 없이 사전에 항목을 추가합니다. (내부 함수)"""
        global _GLOBAL_DICTIONARY, _GLOBAL_DICTIONARY_LOWERCASE

        try:
            if en_value.lower() in _GLOBAL_DICTIONARY_LOWERCASE:
                target_key = _GLOBAL_DICTIONARY_LOWERCASE[en_value.lower()]
                target = _GLOBAL_DICTIONARY[target_key]

                if isinstance(target, list):
                    if ko_value not in target:
                        _GLOBAL_DICTIONARY[target_key].append(ko_value)
                elif isinstance(target, str):
                    if target != ko_value:
                        _GLOBAL_DICTIONARY[target_key] = [target, ko_value]
            else:
                _GLOBAL_DICTIONARY[en_value] = ko_value
                _GLOBAL_DICTIONARY_LOWERCASE[en_value.lower()] = en_value

            return True
        except Exception as e:
            logger.error(f"사전 추가 중 오류 발생: {e}")
            return False

    def get_dictionary(self) -> Dict[str, Any]:
        """현재 사전을 반환합니다."""
        global _GLOBAL_DICTIONARY
        return _GLOBAL_DICTIONARY

    @property
    def translation_dictionary(self) -> Dict[str, Any]:
        """공유 사전에 접근합니다."""
        global _GLOBAL_DICTIONARY
        return _GLOBAL_DICTIONARY

    @property
    def translation_dictionary_lowercase(self) -> Dict[str, str]:
        """공유 사전의 소문자 키 버전에 접근합니다."""
        global _GLOBAL_DICTIONARY_LOWERCASE
        return _GLOBAL_DICTIONARY_LOWERCASE
