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
MINECRAFT_ITEM_CODE_PATTERN = r"[a-z_0-9]+[:.][0-9a-z_./]+"

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

TEMPLATE_TRANSLATE_TEXT = """당신은 마인크래프트 모드팩 번역 전문가입니다. 아래 영어 텍스트를 한국어로 번역해주세요.
모든 지시사항과 규칙을 주의 깊게 읽고 엄격하게 따라주세요.

# 역할
- 마인크래프트 모드팩 번역 전문가
- 영어를 한국어로 정확하고 자연스럽게 번역

# 번역 규칙
{translation_rules}

# 사전 지침
<dictionary_instructions>
{dictionary_instructions}
</dictionary_instructions>{placeholders}

# 참조 사전
<dictionary>
이 사전은 번역 일관성을 위한 참조용입니다.
- 문맥에 맞게 적절히 활용하세요
- 잘못된 번역이 있을 수 있으니 맹신하지 마세요
- 사전에 없는 용어는 자연스러운 한국어로 번역하세요

{dictionary}
</dictionary>

# 형식 지침
<format_instructions>
{format_instructions}
</format_instructions>

# 번역할 텍스트
<text_to_translate>
{text}
</text_to_translate>

# 출력 형식
번역된 텍스트만 제공해 주세요. 설명이나 주석을 추가하지 마세요.
{additional_rules}
"""

RULES_FOR_PLACEHOLDER = """<translation_rules>
# 플레이스홀더 규칙
1. [P숫자] 형식의 플레이스홀더는 절대 수정/번역/삭제하지 말 것
2. 원본에 없는 [P숫자] 토큰을 임의로 추가하지 말 것
3. 플레이스홀더의 위치를 원본과 정확히 동일하게 유지할 것

# 번역 규칙
1. 원문의 의미를 정확하게 전달하는 자연스러운 한국어로 번역할 것
2. 문맥을 고려하여 일관된 용어를 사용할 것
3. 고유명사, 기술 용어, 게임 내 용어는 발음을 정확하게 한글로 표기할 것 
   (예: "Thermal Expansion" → "써멀 익스팬션")
4. 가능한 모든 영어를 한국어로 번역하고, 불필요하게 영어를 유지하지 말 것
5. 사전(dictionary)은 참조용일 뿐, 모든 경우에서 따라하려 하지 말 것
6. 사전에 없는 단어는 자연스러운 한국어로 번역할 것
7. 사전의 번역이 부적절하다면 더 나은 번역으로 대체할 것
8. 어색하게 한국어와 영어를 섞어서 사용하지 말 것
</translation_rules>

<placeholders_rules>
# 플레이스홀더 사용 예시
✓ 올바른 예: 'This is [P1]test[P2]' → '이것은 [P1]테스트[P2]입니다.'
✗ 잘못된 예: 'This is [P1]test[P2]' → '[P1]이것은 테스트[P2]입니다.'
✗ 잘못된 예: 'This is [P1]test[P2]' → '이것은 테스트[P1]입니다.[P2]'
✗ 잘못된 예: 'This is [P1]test[P2]' → '이것은 테스트[P1][P2]입니다.'

중요: 플레이스홀더가 누락되거나 위치가 변경되면 게임에서 오류가 발생합니다.
각 플레이스홀더의 정확한 위치를 원본과 동일하게 유지하세요.
</placeholders_rules>"""

RULES_FOR_NO_PLACEHOLDER = """<translation_rules>
# 번역 규칙
1. 원문의 의미를 정확하게 전달하는 자연스러운 한국어로 번역할 것
2. 문맥을 고려하여 일관된 용어를 사용할 것
3. 고유명사, 기술 용어, 게임 내 용어는 발음을 정확하게 한글로 표기할 것
   (예: "Thermal Expansion" → "써멀 익스팬션")
4. 가능한 모든 영어를 한국어로 번역하고, 불필요하게 영어를 유지하지 말 것
5. 사전(dictionary)은 참조용일 뿐, 모든 경우에서 따라하려 하지 말 것
6. 사전에 없는 단어는 자연스러운 한국어로 번역할 것
7. 사전의 번역이 부적절하다면 더 나은 번역으로 대체할 것
8. 어색하게 한국어와 영어를 섞어서 사용하지 말 것
</translation_rules>"""

DICTIONARY_INSTRUCTIONS = """# 사전 업데이트 지침
1. 번역 중 중요한 용어를 발견하면 new_dictionary_entries 목록에 추가하세요.
2. 실제 번역에 사용된 단어만 ko에 추가하세요.
3. 단일 용어만 추가하고 문장은 추가하지 마세요.

## 올바른 형식
✓ {"en": "Iridium", "ko": "이리듐"}
✓ {"en": "Iridium", "ko": "Iridium"}

## 잘못된 형식
✗ {"en": "Crafting Table Recipe", "ko": "제작대 레시피"} (문장)"""

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
