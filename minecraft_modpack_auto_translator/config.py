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
MINECRAFT_ITEM_CODE_PATTERN = r"[a-zA-Z_0-9]+[:.][0-9a-zA-Z_./]*[a-zA-Z]"

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

TEMPLATE_TRANSLATE_TEXT = """\
당신은 번역 전문가입니다. 아래 지침에 따라 영어 텍스트를 한국어로 번역하세요.

<translation_rules>
{translation_rules}
</translation_rules>

<dictionary_instructions>
{dictionary_instructions}
</dictionary_instructions>{placeholders}

<dictionary>
{dictionary}
</dictionary>

<format_instructions>
{format_instructions}
</format_instructions>

<text_to_translate>
{text}
</text_to_translate>

{additional_rules}
"""

RULES_FOR_PLACEHOLDER = """<translation_rules>
1. **플레이스홀더 유지**  
   - `[P숫자]` 형식의 토큰은 **절대** 수정·번역·삭제하지 않습니다.  
   - 원본에 없던 `[P숫자]` 토큰을 **추가**하지 않습니다.  
   - 문장 또는 단어의 시작·끝에 플레이스홀더가 있으면, **원본과 동일한 위치**에 유지합니다.

2. **의미 전달 & 자연스러움**  
   - 원문의 의미를 충실히 전달하되, **자연스러운 한국어**로 표현합니다.

3. **고유명사·전문용어 음차 표기**  
   - 고유명사, 기술 용어, 게임 내 용어 등은 원어 발음을 살려 **한글 음차**로 표기합니다.  
     - 예: “Thermal Expansion” → “써멀 익스팬션”

4. **용어집 활용**  
   - 제공된 용어집은 **일관성 참고용**입니다.  
   - 단어를 그대로 복사하지 말고, **문맥에 맞게 수정**하여 사용하세요.  
   - 용어집에 없는 단어는 **문맥에 맞는 자연스러운 한국어**로 번역합니다.  
   - 용어집 번역이 부적절하면, **수정**하여 사용하세요.

5. **일반 어휘 한국어화**  
   - 일반 동사, 형용사, 부사 등은 고유명사나 특정 게임 용어가 아닌 이상 **반드시 한국어**로 번역합니다.  
     - 올바른 예: “Enter” → “입장하세요” 또는 “들어가세요”  
     - 잘못된 예: “Enter하세요”
</translation_rules>

<placeholders_rules>
1. 플레이스홀더(`[P숫자]`)를 절대 수정, 번역, 삭제하지 마세요.
2. 플레이스홀더는 원본 텍스트와 동일한 위치에 배치해야 합니다.
3. 예시: 'This is [P1]test[P2]' -> '이것은 [P1]테스트[P2]입니다.' (O)
4. 예시: 'This is [P1]test[P2]' -> '[P1]이것은 테스트[P2]입니다.' (X - 위치 변경)
5. 예시: 'This is [P1]test[P2]' -> '이것은 테스트[P1]입니다.[P2]' (X - 위치 변경)
6. 예시: 'This is [P1]test[P2]' -> '이것은 테스트[P1][P2]입니다.' (X - 위치 변경)

플레이스홀더가 누락되면 게임 실행 시 오류가 발생할 수 있습니다.
번역 시 각 플레이스홀더의 정확한 위치를 반드시 유지해 주세요.
</placeholders_rules>"""

RULES_FOR_NO_PLACEHOLDER = """<translation_rules>
1. **의미 전달 & 자연스러움**  
   - 원문의 의미를 충실히 전달하되, **자연스러운 한국어**로 표현합니다.

2. **고유명사·전문용어 음차 표기**  
   - 고유명사, 기술 용어, 게임 내 용어 등은 원어 발음을 살려 **한글 음차**로 표기합니다.  
     - 예: “Thermal Expansion” → “써멀 익스팬션”

3. **용어집 활용**  
   - 제공된 용어집은 **일관성 참고용**입니다.  
   - 단어를 그대로 복사하지 말고, **문맥에 맞게 수정**하여 사용하세요.  
   - 용어집에 없는 단어는 **문맥에 맞는 자연스러운 한국어**로 번역합니다.  
   - 용어집 번역이 부적절하면, **수정**하여 사용하세요.

4. **일반 어휘 한국어화**  
   - 일반 동사, 형용사, 부사 등은 고유명사나 특정 게임 용어가 아닌 이상 **반드시 한국어**로 번역합니다.  
     - 올바른 예: “Enter” → “입장하세요” 또는 “들어가세요”  
     - 잘못된 예: “Enter하세요”
</translation_rules>"""

DICTIONARY_INSTRUCTIONS = """1. 번역 중 중요하다고 생각되는 용어를 발견하면 `new_dictionary_entries` 목록에 추가해 주세요.
2. 한국어 번역(`ko`) 항목에는 실제 번역에 사용된 단어를 넣어주세요.

올바른 예시:
O {"en": "Iridium", "ko": "이리듐"}
O {"en": "Iridium", "ko": "Iridium"}

잘못된 예시:
X {"en": "Crafting Table Recipe", "ko": "제작대 레시피"} (문장 형태는 지양해주세요.)"""

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
