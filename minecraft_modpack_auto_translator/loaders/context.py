from pydantic import BaseModel


class TranslationContext(BaseModel):
    translation_graph: object
    custom_dictionary_dict: dict
    llm: object = None
    registry: object

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
        if self.translation_dictionary is None:
            self.translation_dictionary = self.custom_dictionary_dict.copy()
        if self.translation_dictionary_lowercase is None:
            self.translation_dictionary_lowercase = {
                k.lower(): k for k, v in self.translation_dictionary.items()
            }

    def add_to_dictionary(self, en_value, ko_value):
        """번역 사전에 새 항목을 추가합니다."""
        self.initialize_dictionaries()

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
            import logging

            logging.getLogger(__name__).error(f"사전 추가 중 오류 발생: {e}")
            return False

    def get_dictionary(self):
        """현재 번역 사전을 반환합니다."""
        self.initialize_dictionaries()
        return self.translation_dictionary
