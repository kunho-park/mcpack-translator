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
C_PLACEHOLDER_PATTERN = r"%(?:[sd]|[0-9]+\$s)"
ITEM_PLACEHOLDER_PATTERN = r"\$\([^)]*\)"
JSON_PLACEHOLDER_PATTERN = r"\{(?:[^{}]|(?R))*\}"
HTML_TAG_PATTERN = r"<[^>]*>"
# 연속된 점(.)이나 슬래시(/)를 허용하지 않고, 경로가 영숫자나 밑줄(_)로 시작하고 끝나도록 수정된 패턴
MINECRAFT_ITEM_CODE_PATTERN = r"((\[[a-zA-Z_0-9]+[:.]([0-9a-zA-Z_]+([./][0-9a-zA-Z_]+)*)\])|([a-zA-Z_0-9]+[:.]([0-9a-zA-Z_]+([./][0-9a-zA-Z_]+)*)))"

SQUARE_BRACKET_TAG_PATTERN = r"\[[A-Za-z0-9_]+\]"

ADDED_DICTIONARY_ENTRIES = []

DIR_FILTER_WHITELIST = [
    "/ftbquests/quests/chapters/",
    "/ftbquests/quests/reward_tables/",
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

TEMPLATE_TRANSLATE_TEXT = """당신은 한국어 **게임 현지화에 매우 능숙한 전문가**입니다. 당신의 임무는 원문의 의도, 문화적 뉘앙스, 게임 고유의 분위기를 살려 게임 텍스트를 자연스럽고 수준 높은 한국어로 번역하는 것입니다. 
중국어, 일본어의 사용은 엄격히 금지합니다.
제공된 모든 지침을 엄격히 준수해야 합니다.

{translation_rules}

<dictionary_instructions>
{dictionary_instructions}
</dictionary_instructions>{placeholders}

<dictionary>
### 용어집 (문맥에 맞게 사용 - 맹신 금지) ###
잘못된 용어가 있을 수 있으므로, 용어집을 참고하되 필요에 따라 용어를 조정해야 합니다. 
용어집에 없는 용어는 자연스러운 한국어로 번역해야 합니다.

{dictionary}
</dictionary>

<format_instructions>
### 서식 규칙 ###
{format_instructions}
</format_instructions>

<source_text>
{text}
</source_text>

{additional_rules}
"""

RULES_FOR_PLACEHOLDER = """<translation_rules>
### 핵심 번역 지침 ###
1.  **플레이스홀더 무결성**: 모든 `[P<숫자>]` 토큰을 **정확히** 보존해야 합니다. 수정, 번역, 삭제하거나 새로 추가해서는 안 됩니다. 단어/문장 내 원래 위치를 유지해야 합니다.
2.  **단위 무결성**: m, s, kg, XP, %, °C, °F, km, mm, HP, MP 등 **단위 및 수치 기호**는 반드시 원본 그대로 유지해야 합니다. 단위와 수치는 번역하지 마세요.
3.  **자연스러운 한국어**: 자연스럽고 관용적인 한국어로 충실하게 번역해야 합니다.
4.  **용어집 활용**: 용어집을 참고하되, 필요에 따라 용어를 조정해야 합니다. 용어집에 없는 용어는 자연스러운 한국어로 번역해야 합니다.
5.  **혼용 금지**: 영단어를 반드시 유지해야 하는 경우(예: "OK")를 제외하고는 한국어만 사용해야 합니다.
    *   틀린 예: "이름을 enter하세요"
    *   옳은 예: "이름을 입력하세요"
6.  **대소문자**: 유지되는 영단어, 약어, 고유 명사의 경우 원문 영어의 대소문자 표기를 따라야 합니다.
</translation_rules>

<placeholders_rules>
### 플레이스홀더 상세(`[P<숫자>]`) ###
1.  **중요**: 플레이스홀더를 절대 변경, 번역, 제거해서는 안 됩니다.
2.  **위치**: 플레이스홀더를 **정확히** 원래 위치에 유지해야 합니다.
    *   옳은 예: "This is [P1]test[P2]" → "이것은 [P1]테스트[P2]입니다."
    *   틀린 예 (위치 변경): "This is [P1]test[P2]" → "[P1]이것은 테스트[P2]입니다."
    *   틀린 예 (병합): "This is [P1]test[P2]" → "이것은 테스트[P1][P2]입니다."
    플레이스홀더를 잘못 배치하거나 생략하면 게임이 손상됩니다. 원래 위치를 유지해야 합니다.
    플레이스홀더는 번역내에 색상 코드 및 여러 효과 혹은 데이터를 포함합니다. 이를 고려하여 번역하세요.
</placeholders_rules>"""

RULES_FOR_NO_PLACEHOLDER = """<translation_rules>
### 핵심 번역 지침 ###
1.  **단위 무결성**: m, s, kg, XP, %, °C, °F, km, mm, HP, MP 등 **단위 및 수치 기호**는 반드시 원본 그대로 유지해야 합니다. 단위와 수치는 번역하지 마세요.
2.  **자연스러운 한국어**: 자연스럽고 관용적인 한국어로 충실하게 번역해야 합니다.
3.  **용어집 활용**: 용어집을 참고하되, 필요에 따라 용어를 조정해야 합니다. 용어집에 없는 용어는 자연스러운 한국어로 번역해야 합니다.
4.  **혼용 금지**: 영단어를 반드시 유지해야 하는 경우(예: "OK")를 제외하고는 한국어만 사용해야 합니다.
    *   틀린 예: "이름을 enter하세요"
    *   옳은 예: "이름을 입력하세요"
5.  **대소문자**: 유지되는 영단어, 약어, 고유 명사의 경우 원문 영어의 대소문자 표기를 따라야 합니다.
</translation_rules>
"""

DICTIONARY_INSTRUCTIONS = """### 용어집 기여 지침 ###
1.  핵심 용어가 용어집에 포함되어야 한다면 `new_dictionary_entries`에 추가하십시오.
2.  `ko` 필드에 최종 한국어 번역을 제공하십시오.
3.  `ko` 필드에는 한국어만 사용하십시오 (예: `{"en": "Crafting Table", "ko": "조합대"}`. `"크래프팅 Table"`과 같이 사용하지 마십시오).
4.  단어나 짧은 구문을 등록하고, 전체 문장은 등록하지 마십시오.

### 예시 ###
O `{"en": "Iridium", "ko": "이리듐"}`
(필수적인 경우에만 `ko` 필드에 영어를 사용하십시오. 예: `{"en": "OK", "ko": "OK"}`)
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
