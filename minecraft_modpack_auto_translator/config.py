import json
import os

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 언어 파일 경로
LANGUAGE_FILES_PATH = os.path.join(os.path.dirname(__file__), "assets/versions/1.21.5")
OFFICIAL_EN_LANG_FILE = json.load(
    open(os.path.join(LANGUAGE_FILES_PATH, "en_us.json"), "r", encoding="utf-8")
)
OFFICIAL_KO_LANG_FILE = json.load(
    open(os.path.join(LANGUAGE_FILES_PATH, "ko_kr.json"), "r", encoding="utf-8")
)

FORMAT_CODE_PATTERN = r"[§&][0-9a-fk-or]"
C_PLACEHOLDER_PATTERN = r"%(?:[sd]|1\$s)"
ITEM_PLACEHOLDER_PATTERN = r"\$\([^)]*\)"
JSON_PLACEHOLDER_PATTERN = r"\{(?:[^{}]|(?R))*\}"
HTML_TAG_PATTERN = r"<[^>]*>"
MINECRAFT_ITEM_CODE_PATTERN = r"[a-z_]+:[a-z_/]+"

ADDED_DICTIONARY_ENTRIES = []

DIR_FILTER_WHITELIST = [
    "/ftbquests/quests/chapters/",
]

# 기본 영어 단어 블랙리스트
DICTIONARY_BLACKLIST = [
    "with",
    "is",
    "the",
    "and",
    "of",
    "to",
    "a",
    "in",
    "for",
    "on",
    "by",
    "at",
    "from",
    "as",
    "an",
    "or",
    "if",
    "be",
    "it",
    "not",
    "this",
    "that",
    "are",
    "has",
    "was",
    "will",
    "can",
    "you",
    "your",
    "my",
    "his",
    "her",
    "their",
    "our",
    "its",
    "we",
    "they",
    "he",
    "she",
    "who",
    "what",
    "when",
    "where",
    "why",
    "how",
    "all",
    "any",
    "some",
    "no",
]

TEMPLATE_TRANSLATE_TEXT = """당신은 마인크래프트 번역 전문가입니다. 영어 텍스트를 한국어로 번역해야 합니다.
모든 경우에 아래 규칙을 엄격히 따라야 합니다.

{translation_rules}

<dictionary_instructions>
{dictionary_instructions}
</dictionary_instructions>{placeholders}

<dictionary>
번역 일관성을 위한 참조용 사전입니다. 번역 시 참고하세요.
잘못된 번역이 있을 수 있습니다. 
사전을 맹신하지 말고 문맥에 맞게 조정하세요.
단어가 여러개 있을시 앞에 있는 단어를 더 중시하세요.

{dictionary}
</dictionary>

<format_instructions>
{format_instructions}
</format_instructions>

<text_to_translate>
{text}
</text_to_translate>{additional_rules}
"""

RULES_FOR_PLACEHOLDER = """<translation_rules>
1. [P숫자] 형식의 플레이스홀더 토큰을 절대 수정, 번역 또는 삭제하지 마세요.
2. 원본에 없는 [P숫자] 형식의 토큰을 새로 만들지 마세요.
3. 단어나 문장의 시작/끝에 플레이스홀더가 있는 경우, 해당 토큰을 정확히 유지하세요.
4. 뜻을 정확하게 유지하도록 자연스럽게 번역하세요.
5. 문맥을 파악하고 자연스럽게 번역하는것이 중요합니다.
6. 뜻을 모르는 영어를 한글로 번역하는 경우 발음을 정확하게 유지하세요. 특히 고유명사, 기술 용어, 게임 내 고유 용어는 원본 발음을 최대한 정확하게 한글로 표기하세요.
7. dictionary은 참조용일 뿐이며, 직접 복사하지 마세요.
8. dictionary에 존재하지 않는 단어는 "자연스러운 한국어"로 번역하세요.
9. dictionary에서 단어를 사용할 경우 문법에 맞게 자연스럽게 활용하세요. dictionary의 번역을 맹신하지 말고 문맥에 맞게 조정하세요.
10. dictionary에 사용된 단어가 틀렸을 경우, 변경하여 활용하세요.
11. "Thermal Expansion"과 같은 고유 제품명이나 모드명은 원어 발음에 충실하게 "써멀 익스팬션"으로 번역하세요.
12. 가능한 모든 영어 단어를 한국어로 번역하고, 영어를 그대로 유지하는 것을 최소화하세요. (영어로 유지해야 하는건 유지)
13. 대소문자를 문법에 맞게 정확하게 지키세요.
</translation_rules>

<placeholders_rules>
1. 플레이스홀더를 절대 수정, 번역 또는 삭제하지 마세요.
2. 플레이스홀더를 원본 텍스트에 나타나는 것과 동일한 위치에 배치하세요.
3. 예시: 'This is [P1]test[P2]' -> '이것은 [P1]테스트[P2] 입니다.' (O)
4. 예시: 'This is [P1]test[P2]' -> '[P1]이것은 테스트 [P2] 입니다.' (X)
5. 예시: 'This is [P1]test[P2]' -> '이것은 테스트[P1] 입니다.[P2]' (X)
6. 예시: 'This is [P1]test[P2]' -> '이것은 테스트[P1][P2] 입니다.' (X)

플레이스홀더가 누락되면 게임에서 오류가 발생합니다.
번역할 때 각 플레이스홀더의 정확한 위치를 유지하세요.
</placeholders_rules>"""

RULES_FOR_NO_PLACEHOLDER = """<translation_rules>
1. 뜻을 정확하게 유지하도록 자연스럽게 번역하세요.
2. 문맥을 파악하고 자연스럽게 번역하는것이 중요합니다.
3. 뜻을 모르는 영어를 한글로 번역하는 경우 발음을 정확하게 유지하세요. 특히 고유명사, 기술 용어, 게임 내 고유 용어는 원본 발음을 최대한 정확하게 한글로 표기하세요.
4. dictionary은 참조용일 뿐이며, 직접 복사하지 마세요.
5. dictionary에 존재하지 않는 단어는 자연스러운 한국어로 번역하세요.
6. dictionary에서 단어를 사용할 경우 문법에 맞게 자연스럽게 활용하세요. dictionary의 번역을 맹신하지 말고 문맥에 맞게 조정하세요.
7. dictionary에 사용된 단어가 틀렸을 경우, 변경하여 활용하세요.
8. "Thermal Expansion"과 같은 고유 제품명이나 모드명은 원어 발음에 충실하게 "써멀 익스팬션"으로 번역하세요.
9. 가능한 모든 영어 단어를 한국어로 번역하고, 영어를 그대로 유지하는 것을 최소화하세요. (영어로 유지해야 하는건 유지)
10. 대소문자를 문법에 맞게 정확하게 지키세요.
</translation_rules>"""

DICTIONARY_INSTRUCTIONS = """1. 번역 중 중요한 용어를 발견하면 new_dictionary_entries 목록에 추가하세요.
2. 실제 번역에 사용된 단어로 ko에 추가하세요.

예시:
O {"en": "Iridium", "ko": "이리듐"}
O {"en": "Iridium", "ko": "Iridium"}
X {"en": "Crafting Table Recipe", "ko": "제작대 레시피"} (문장)"""

DICTIONARY_PREFIX_WHITELIST = [
    "item",
    "block",
    "entity",
    "effect",
    "enchantment",
    "biome",
    "structure",
    "dimension",
    "advancement",
    "potion",
    "mob",
    "ore",
    "tool",
    "weapon",
    "armor",
    "food",
    "attribute",
    "material",
    "itemGroup",
    "container",
    "spell",
    "key.categories",
]

DICTIONARY_SUFFIX_BLACKLIST = ["desc", "info", "tooltip", "description", "guide"]
