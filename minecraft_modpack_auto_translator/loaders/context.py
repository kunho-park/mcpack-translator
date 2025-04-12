import asyncio
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TranslationContext(BaseModel):
    translation_graph: object
    custom_dictionary_dict: dict
    llm: object = None
    registry: object

    # 공유를 위한 클래스 변수
    _shared_dictionary: dict = {}
    _shared_dictionary_lowercase: dict = {}
    _lock = asyncio.Lock()

    # 번역 사전 관리를 위한 속성 추가
    translation_dictionary: dict = None
    translation_dictionary_lowercase: dict = None

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    def get(self, key, default=None):
        return getattr(self, key, default)

    def initialize_dictionaries(self):
        """초기 사전 데이터를 설정합니다."""
        # 클래스 공유 사전이 비어있으면 초기화
        if not TranslationContext._shared_dictionary and self.custom_dictionary_dict:
            TranslationContext._shared_dictionary = self.custom_dictionary_dict.copy()
            TranslationContext._shared_dictionary_lowercase = {
                k.lower(): k for k, v in self.custom_dictionary_dict.items()
            }

        # 인스턴스 사전을 공유 사전으로 설정
        self.translation_dictionary = TranslationContext._shared_dictionary
        self.translation_dictionary_lowercase = (
            TranslationContext._shared_dictionary_lowercase
        )

    async def async_add_to_dictionary(self, en_value, ko_value):
        """번역 사전에 새 항목을 비동기적으로 추가합니다."""
        self.initialize_dictionaries()

        async with TranslationContext._lock:
            return self._add_to_dictionary_unsafe(en_value, ko_value)

    def add_to_dictionary(self, en_value, ko_value):
        """번역 사전에 새 항목을 추가합니다."""
        self.initialize_dictionaries()
        return self._add_to_dictionary_unsafe(en_value, ko_value)

    def _add_to_dictionary_unsafe(self, en_value, ko_value):
        """락 없이 사전에 항목을 추가합니다 (내부 사용)."""
        try:
            if en_value.lower() in self.translation_dictionary_lowercase:
                target = self.translation_dictionary[
                    self.translation_dictionary_lowercase[en_value.lower()]
                ]
                if isinstance(target, list):
                    if ko_value not in target:
                        self.translation_dictionary[
                            self.translation_dictionary_lowercase[en_value.lower()]
                        ].append(ko_value)
                elif isinstance(target, str):
                    if (
                        self.translation_dictionary[
                            self.translation_dictionary_lowercase[en_value.lower()]
                        ]
                        != ko_value
                    ):
                        self.translation_dictionary[
                            self.translation_dictionary_lowercase[en_value.lower()]
                        ] = [
                            self.translation_dictionary[
                                self.translation_dictionary_lowercase[en_value.lower()]
                            ],
                            ko_value,
                        ]
            else:
                self.translation_dictionary[en_value] = ko_value
                self.translation_dictionary_lowercase[en_value.lower()] = en_value

            return True
        except Exception as e:
            logger.error(f"사전 추가 중 오류 발생: {e}")
            return False

    def get_dictionary(self):
        """현재 번역 사전을 반환합니다."""
        self.initialize_dictionaries()
        return self.translation_dictionary
