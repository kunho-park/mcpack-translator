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
# 연속된 점(.)이나 슬래시(/)를 허용하지 않고, 경로가 영숫자나 밑줄(_)로 시작하고 끝나도록 수정된 패턴
MINECRAFT_ITEM_CODE_PATTERN = r"((\[[a-zA-Z_0-9]+[:.]([0-9a-zA-Z_]+([./][0-9a-zA-Z_]+)*)\])|([a-zA-Z_0-9]+[:.]([0-9a-zA-Z_]+([./][0-9a-zA-Z_]+)*)))"
# 대괄호 태그 패턴 (그룹1: 여는 태그, 그룹2: 내용, 그룹3: 닫는 태그 감지)
SQUARE_BRACKET_TAG_PATTERN = r"(\[[a-z0-9_]+\])(.*?)?(\[/[a-z0-9_]+\])"


ADDED_DICTIONARY_ENTRIES = []

DIR_FILTER_WHITELIST = [
    "/ftbquests/quests/chapters/",
    "/paxi/datapacks/",
    "/paxi/resourcepacks/",
    "/puffish_skills/categories/",
    "/openloader",
    "/global_packs/required_data/",
    "/origins/",
    "/powers/",
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

TEMPLATE_TRANSLATE_TEXT = """You are a **highly experienced game localization expert** for Korean. Your mission is to translate game text to a natural, high-quality Korean, capturing the original intent, cultural nuances, and game-specific atmosphere. Adhere strictly to all provided guidelines and placeholders.

{translation_rules}

<dictionary_instructions>
{dictionary_instructions}
</dictionary_instructions>{placeholders}

<dictionary>
### Glossary (Contextual Use - Do Not Blindly Trust) ###
{dictionary}
</dictionary>

<format_instructions>
### Formatting Rules ###
{format_instructions}
</format_instructions>

<source_text>
{text}
</source_text>

{additional_rules}
"""

RULES_FOR_PLACEHOLDER = """<translation_rules>
### Core Translation Directives ###
1.  **Placeholder Integrity**: Preserve all `[P<number>]` tokens EXACTLY. Do not modify, translate, delete, or add new ones. Maintain their original position within words/sentences.
2.  **Natural Korean**: Translate faithfully into smooth, idiomatic Korean.
3.  **Glossary Usage**: Refer to the glossary, adapting terms as needed. For non-glossary terms, provide natural Korean translations.
4.  **No Mixed Languages**: Output Korean only, unless an English term must be retained (e.g., "OK").
    *   Incorrect: "이름을 enter하세요"
    *   Correct: "이름을 입력하세요"
5.  **Capitalization**: Match original English capitalization for retained terms, acronyms, and proper nouns.
</translation_rules>

<placeholders_rules>
### Placeholder Specifics (`[P<number>]`) ###
1.  **Critical**: NEVER alter, translate, or remove placeholders.
2.  **Position**: Keep placeholders in their EXACT original positions.
    *   Correct: "This is [P1]test[P2]" → "이것은 [P1]테스트[P2]입니다."
    *   Incorrect (Position Changed): "This is [P1]test[P2]" → "[P1]이것은 테스트[P2]입니다."
    *   Incorrect (Merged): "This is [P1]test[P2]" → "이것은 테스트[P1][P2]입니다."
    Misplacing/omitting placeholders BREAKS THE GAME. Maintain original placement.
</placeholders_rules>"""

RULES_FOR_NO_PLACEHOLDER = """<translation_rules>
### Core Translation Directives ###
1.  **Natural Korean**: Translate faithfully into smooth, idiomatic Korean.
2.  **Glossary Usage**: Refer to the glossary, adapting terms as needed. For non-glossary terms, provide natural Korean translations.
3.  **No Mixed Languages**: Output Korean only, unless an English term must be retained (e.g., "OK").
    *   Incorrect: "이름을 enter하세요"
    *   Correct: "이름을 입력하세요"
4.  **Capitalization**: Match original English capitalization for retained terms, acronyms, and proper nouns.
</translation_rules>"""

DICTIONARY_INSTRUCTIONS = """### Glossary Contribution Guidelines ###
1.  If a key term should be in the glossary, add it to `new_dictionary_entries`.
2.  Provide the final Korean translation in the `ko` field.
3.  Korean only in `ko` field (e.g., `{"en": "Crafting Table", "ko": "크래프팅 테이블"}` not `"크래프팅 Table"`).
4.  Register words or short phrases, not full sentences.

### Example ###
O `{"en": "Iridium", "ko": "이리듐"}`
(Use English in `ko` only if essential, e.g., `{"en": "OK", "ko": "OK"}`)
"""

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
