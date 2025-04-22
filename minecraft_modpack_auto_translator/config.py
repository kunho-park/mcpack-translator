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
    "/paxi/datapacks/",
    "/paxi/resourcepacks/",
    "/puffish_skills/categories/",
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
당신은 **게임 로컬라이제이션 전문가**입니다. 아래 가이드라인을 100% 준수하여 번역 프롬프트를 작성하세요.

{translation_rules}

<dictionary_instructions>
{dictionary_instructions}
</dictionary_instructions>{placeholders}

<dictionary>
{dictionary}
</dictionary>

<format_instructions>
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
1. **플레이스홀더 유지**  
   - `[P숫자]` 형식의 토큰은 **절대** 수정·번역·삭제하지 않습니다.  
   - 원본에 없던 `[P숫자]` 토큰을 **추가**하지 않습니다.  
   - 문장 또는 단어의 시작·끝에 플레이스홀더가 있으면, **원본과 동일한 위치**에 유지합니다.

2. **의미 전달 & 자연스러움**  
   - 원문의 의미를 충실히 살리되, **자연스럽고 매끄러운 한국어**로 번역하세요.

3. **고유명사·전문용어 음차 표기**  
   - 고유명사, 기술 용어, 게임 내 용어 등은 원어 발음을 살려 **한글 음차**로 표기하세요.  
     - 예: Thermal Expansion → 써멀 익스팬션

4. **용어집 활용**  
   - 제공된 용어집을 참고하되, **문맥에 맞게 수정**하여 사용하세요.  
   - 용어집에 없는 단어는 **자연스러운 한국어**로 번역하세요.

5. **영어와 한국어의 혼용 금지**  
   - **영어와 한국어를 혼합하여 사용하는 것은 엄격히 금지됩니다.**  
   - 꼭 영어로 사용해야 하는 경우가 아니라면 한국어를 사용하세요.
     - 잘못된 번역 예시:  
       - "Enter your name" → "이름을 enter하세요" 
       - "Press Start" → "start합니다"  
     - 올바른 번역 예시:  
       - "Enter your name" → "이름을 입력하세요" (완전한 한국어)  
       - "Press Start" → "시작 버튼을 누르세요" (문맥에 맞는 자연스러운 한국어)

6. **다른 언어 사용 엄격 금지**
   - 번역 결과는 반드시 **한국어** 또는 **영어**로만 작성해야 합니다.
   - 중국어, 일본어, 프랑스어 등 다른 언어는 절대 사용하지 마세요.
   - 예외적으로 게임 내 고유명사나 브랜드명 등은 원어 그대로 표기할 수 있습니다.
     - 예: "Sakura" → "사쿠라" (X, 원어 유지) / "Sakura" → "Sakura" (O)
   - 영어를 한국어로 번역할 때는 완전한 한국어 문장을 사용해야 합니다.
     - 예: "Open Inventory" → "인벤토리 열기" (O)
     - 예: "Open Inventory" → "Open 인벤토리" (X, 혼합 사용 금지)
</translation_rules>

<placeholders_rules>
1. 플레이스홀더(`[P숫자]`)를 절대 수정, 번역, 삭제하지 마세요.
2. 플레이스홀더는 원본 텍스트와 동일한 위치에 배치해야 합니다.
3. 예시: 'This is [P1]test[P2]' → '이것은 [P1]테스트[P2]입니다.' (O)
4. 예시: 'This is [P1]test[P2]' → '[P1]이것은 테스트[P2]입니다.' (X - 위치 변경)
5. 예시: 'This is [P1]test[P2]' → '이것은 테스트[P1]입니다.[P2]' (X - 위치 변경)
6. 예시: 'This is [P1]test[P2]' → '이것은 테스트[P1][P2]입니다.' (X - 위치 변경)

플레이스홀더가 누락되면 게임 실행 시 오류가 발생할 수 있습니다.
번역 시 각 플레이스홀더의 정확한 위치를 반드시 유지해 주세요.
</placeholders_rules>"""

RULES_FOR_NO_PLACEHOLDER = """<translation_rules>
1. **의미 전달 & 자연스러움**  
   - 원문의 의미를 충실히 살리되, **자연스럽고 매끄러운 한국어**로 번역하세요.

2. **고유명사·전문용어 음차 표기**  
   - 고유명사, 기술 용어, 게임 내 용어 등은 원어 발음을 살려 **한글 음차**로 표기하세요.  
     - 예: Thermal Expansion → 써멀 익스팬션

3. **용어집 활용**  
   - 제공된 용어집을 참고하되, **문맥에 맞게 수정**하여 사용하세요.  
   - 용어집에 없는 단어는 **자연스러운 한국어**로 번역하세요.

4. **영어와 한국어의 혼용 금지**  
   - **영어와 한국어를 혼합하여 사용하는 것은 엄격히 금지됩니다.**  
   - 꼭 영어로 사용해야 하는 경우가 아니라면 한국어를 사용하세요.
     - 잘못된 번역 예시:  
       - "Enter your name" → "이름을 enter하세요" 
       - "Press Start" → "start합니다"  
     - 올바른 번역 예시:  
       - "Enter your name" → "이름을 입력하세요" (완전한 한국어)  
       - "Press Start" → "시작 버튼을 누르세요" (문맥에 맞는 자연스러운 한국어)

5. **다른 언어 사용 엄격 금지**
   - 번역 결과는 반드시 **한국어** 또는 **영어**로만 작성해야 합니다.
   - 중국어, 일본어, 프랑스어 등 다른 언어는 절대 사용하지 마세요.
   - 영어를 한국어로 번역할 때는 완전한 한국어 문장을 사용해야 합니다.
     - 예: "Open Inventory" → "인벤토리 열기" (O)
     - 예: "Open Inventory" → "Open 인벤토리" (X, 혼합 사용 금지)
</translation_rules>"""
DICTIONARY_INSTRUCTIONS = """1. 사전에 추가할 중요 용어 발견 시 `new_dictionary_entries` 목록에 등록해주세요.
2. `ko` 필드에는 실제 적용된 한국어 번역어를 기입하세요.
3. 영어-한글 혼용은 엄격히 금지합니다 (예: "Crafting Table" → "크래프팅 테이블" (O), "크래프팅 Table" (X))
4. 전문 용어/고유명사는 원어 발음에 충실한 한글 음차를 우선 적용하세요.
   - 예: "Thermal Expansion" → "써멀 익스팬션"
5. 필요한 경우 국제적으로 통용되는 용어/브랜드명은 영어 원형 유지 가능
   - 예: "ID" → "ID" (O)
6. 사전 등록 시 단어/구 단위로 등록하고 문장 형태는 지양하세요.

올바른 예시:
O {"en": "Iridium", "ko": "이리듐"}
O {"en": "Group ID", "ko": "그룹 ID"}

잘못된 예시:
X {"en": "Group ID", "ko": "Group ID"} (영어를 최소한으로 유지하세요.)
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
