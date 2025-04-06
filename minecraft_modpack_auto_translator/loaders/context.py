from pydantic import BaseModel


class TranslationContext(BaseModel):
    translation_graph: object
    custom_dictionary_dict: dict
    llm: object = None
    registry: object

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    def get(self, key, default=None):
        return getattr(self, key, default)
