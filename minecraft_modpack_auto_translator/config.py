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
SQUARE_BRACKET_TAG_PATTERN = r"(\[[a-z0-9_]+\])(.*?)?(\[\/[a-z0-9_]+\])"


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

TEMPLATE_TRANSLATE_TEXT = """Your task is to generate a translation prompt for game localization. You are a **highly experienced game localization expert**, deeply familiar with the unique terminology, atmosphere, and context of video games. Your goal is not just to translate text, but to convey the original intent and enjoyment to Korean gamers in a natural way, considering cultural nuances to provide the highest quality Korean translation. You MUST follow the guidelines below exactly. The audience is an expert in the field. Think step by step. Answer a question given in a natural, human-like manner. Ensure that your answer is unbiased and avoids relying on stereotypes.

{translation_rules}

<dictionary_instructions>
{dictionary_instructions}
</dictionary_instructions>{placeholders}

<dictionary>
###Instruction###
Do not blindly trust these entries. Preserve formatting and capitalization.

###Dictionary###
{dictionary}
</dictionary>

<format_instructions>
###Instruction###
{format_instructions}
</format_instructions>

<translation_key>
{translation_key}
</translation_key>

<translation_text>
{text}
</translation_text>

{additional_rules}
"""

RULES_FOR_PLACEHOLDER = """<translation_rules>
###Instruction###
1. Preserve every placeholder token of the form `[P<number>]`.  
   - Do not modify, translate, or delete any `[P<number>]` tokens.  
   - Do not introduce new `[P<number>]` tokens.  
   - If a placeholder appears at the start or end of a word or sentence, keep it in the exact original position.
   - Placeholders must remain in the same word as the original text.

2. Convey meaning naturally.  
   - Translate faithfully while producing smooth, idiomatic Korean.

3. Use the glossary contextually.  
   - Refer to the provided glossary and adapt entries as needed.  
   - For terms not in the glossary, translate into natural Korean.

4. Prohibit mixed‐language output.  
   - Do not mix English and Korean.  
   - Always produce fully Korean text unless the term must remain in English.  
     - Incorrect: "Enter your name" → "이름을 enter하세요"  
     - Correct: "Enter your name" → "이름을 입력하세요"

5. Ban any other language.  
   - Output only in Korean (or English if specified).  
   - Do not use Chinese, Japanese, French, or any other language.

6. Respect original capitalization.  
   - When retaining English terms, match the source's uppercase/lowercase exactly.  
   - Preserve capitalization for acronyms, proper nouns, and sentence starts.
</translation_rules>

<placeholders_rules>
###Instruction###
1. Never alter, translate, or remove any `[P<number>]` placeholder.  
2. Place each placeholder in the same position as in the source text.  
3. Example (correct):  
   "This is [P1]test[P2]" → "이것은 [P1]테스트[P2]입니다."  
4. Example (incorrect – position changed):  
   "This is [P1]test[P2]" → "[P1]이것은 테스트[P2]입니다."  
5. Example (incorrect – position changed):  
   "This is [P1]test[P2]" → "이것은 테스트[P1]입니다.[P2]"  
6. Example (incorrect – merged placeholders):  
   "This is [P1]test[P2]" → "이것은 테스트[P1][P2]입니다."

Omitting or misplacing placeholders will break the game. You MUST keep every placeholder exactly in its original location.
</placeholders_rules>"""

RULES_FOR_NO_PLACEHOLDER = """<translation_rules>
###Instruction###
1. Convey meaning naturally.  
   - Translate faithfully while producing smooth, idiomatic Korean.

2. Use the glossary contextually.  
   - Refer to the provided glossary and adapt entries as needed.  
   - For terms not in the glossary, translate into natural Korean.

3. Prohibit mixed‐language output.  
   - Do not mix English and Korean.  
   - Always produce fully Korean text unless the term must remain in English.  
     - Incorrect: "Enter your name" → "이름을 enter하세요"  
     - Correct: "Enter your name" → "이름을 입력하세요"

4. Ban any other language.  
   - Output only in Korean (or English if specified).  
   - Do not use Chinese, Japanese, French, or any other language.

5. Respect original capitalization.  
   - When retaining English terms, match the source's uppercase/lowercase exactly.  
   - Preserve capitalization for acronyms, proper nouns, and sentence starts.
</translation_rules>"""

DICTIONARY_INSTRUCTIONS = """###Instruction###
1. When you identify a key term to add to the glossary, record it under `new_dictionary_entries`.  
2. Fill the `ko` field with the finalized Korean translation.  
3. Do not mix English and Korean.  
   - Correct: `{"en": "Crafting Table", "ko": "크래프팅 테이블"}`  
   - Incorrect: `{"en": "Crafting Table", "ko": "크래프팅 Table"}`  
4. Register entries at the word or short phrase level only; avoid sentence-length entries.

###Example###
O `{"en": "Iridium", "ko": "이리듐"}`  
X `{"en": "Group ID", "ko": "Group ID"}` (Use English only when necessary.)  
X `{"en": "Crafting Table Recipe", "ko": "제작대 레시피"}` (Avoid full-sentence entries.)"""

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
