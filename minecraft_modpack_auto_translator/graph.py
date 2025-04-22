import asyncio
import json
import logging
import random
import re
import traceback
from typing import Any, Dict, List

import regex
from dotenv import load_dotenv
from langchain.schema.output_parser import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import BaseOutputParser, PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from .config import (
    C_PLACEHOLDER_PATTERN,
    DICTIONARY_BLACKLIST,
    DICTIONARY_INSTRUCTIONS,
    FORMAT_CODE_PATTERN,
    HTML_TAG_PATTERN,
    ITEM_PLACEHOLDER_PATTERN,
    JSON_PLACEHOLDER_PATTERN,
    MINECRAFT_ITEM_CODE_PATTERN,
    RULES_FOR_NO_PLACEHOLDER,
    RULES_FOR_PLACEHOLDER,
    TEMPLATE_TRANSLATE_TEXT,
)
from .delay_manager import DelayManager
from .loaders import (
    DefaultLoader,
    DictLoader,
    FTBQuestsChapterQuestsLoader,
    FTBQuestsChapterTitleLoader,
    ListLoader,
    LoaderRegistry,
    PatchouliBooksLoader,
    PaxiDatapackLoader,
    PuffishSkillsLoader,
    StringLoader,
    TConstructBooksLoader,
    TranslationContext,
    WhiteListLoader,
)

registry = LoaderRegistry()

# 로더 등록 (우선순위 순서대로)

# 특수 케이스 먼저
registry.register(WhiteListLoader())
registry.register(PatchouliBooksLoader())
registry.register(FTBQuestsChapterQuestsLoader())
registry.register(FTBQuestsChapterTitleLoader())
registry.register(TConstructBooksLoader())
registry.register(PuffishSkillsLoader())
registry.register(PaxiDatapackLoader())

# 일반 케이스
registry.register(ListLoader())
registry.register(StringLoader())
registry.register(DictLoader())
registry.register(DefaultLoader())  # 기본 로더는 항상 마지막

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("translation.log", encoding="utf-8"),
    ],
)

load_dotenv()


# 특수 형식 (색상 코드, 플레이스홀더) 추출 및 보존
def extract_special_formats(text):
    format_codes = [i for i in re.findall(FORMAT_CODE_PATTERN, text) if i != ""]
    c_placeholders = [i for i in re.findall(C_PLACEHOLDER_PATTERN, text) if i != ""]
    json_placeholders = [
        i for i in regex.findall(JSON_PLACEHOLDER_PATTERN, text) if i != ""
    ]
    item_placeholders = [
        i for i in re.findall(ITEM_PLACEHOLDER_PATTERN, text) if i != ""
    ]
    html_tags_placeholders = [i for i in re.findall(HTML_TAG_PATTERN, text) if i != ""]

    # 마인크래프트 아이템 코드 패턴 (예: minecraft:grass)
    minecraft_item_codes = [
        i for i in re.findall(MINECRAFT_ITEM_CODE_PATTERN, text) if i != ""
    ]

    # 모든 특수 형식을 [PLACEHOLDER_N] 형태로 대체
    replaced_text = text
    placeholder_map = {}
    placeholder_count = 0

    for placeholder in (
        html_tags_placeholders
        + item_placeholders
        + json_placeholders
        + format_codes
        + c_placeholders
        + minecraft_item_codes
    ):
        if placeholder in replaced_text:
            placeholder_count += 1
            token = f"[P{placeholder_count}]"
            replaced_text = replaced_text.replace(placeholder, token, 1)
            placeholder_map[token] = placeholder

    return replaced_text, placeholder_map


# 특수 형식 복원
def restore_special_formats(text, placeholder_map):
    restored_text = text

    # 플레이스홀더 복원
    for token, placeholder in placeholder_map.items():
        restored_text = restored_text.replace(token, placeholder)

    return restored_text


# 텍스트 분석 및 특수 형식 추출
async def analyze_text(state):
    text = state["text"]
    replaced_text, placeholder_map = extract_special_formats(text)

    # TranslationContext 객체가 있으면 사전 초기화
    context: TranslationContext = state.get("context")
    if context:
        context.initialize_dictionaries()

    if context.force_keep_line_break:
        newline_placeholder = "[P_NEWLINE]"
        replaced_text = re.sub(r"\n", newline_placeholder, replaced_text)
        placeholder_map[newline_placeholder] = "\n"

    return {
        "text": text,
        "replaced_text": replaced_text,
        "placeholder_map": placeholder_map,
        "extracted_entities": [],
        "context": context,
        "has_error": False,
        "translation_key": state.get("translation_key", ""),
    }


# RAG에서 번역 정보 검색
async def retrieve_translations(state):
    context = state["context"]
    context.initialize_dictionaries()
    translation_dictionary = context.translation_dictionary

    dictionary = []
    text = state["replaced_text"]
    normalized_text = text.lower()

    # replaced_text = text

    # for k, i in translation_dictionary.items():
    #     if isinstance(i, list):
    #         for j in i:
    #             if len(j) < 3:
    #                 continue
    #             if j in replaced_text:
    #                 replaced_text = replaced_text.replace(j, "__REPLACE__")
    #                 dictionary.append(f"{k} -> {j}")
    #     else:
    #         if len(i) < 3:
    #             continue
    #         if i in replaced_text:
    #             replaced_text = replaced_text.replace(i, "__REPLACE__")
    #             dictionary.append(f"{k} -> {i}")

    filtered_english_words = [
        i
        for i in re.findall(r"\b[a-zA-Z]+\b", normalized_text)
        if i not in DICTIONARY_BLACKLIST
    ]
    # s, 's로 끝나는 단어들의 원형도 추가
    additional_words = []
    for word in filtered_english_words:
        # 정규식을 사용하여 's 또는 s로 끝나는 단어 처리
        base_word = re.sub(r"'s$|s$", "", word)
        if (
            base_word != word
            and base_word not in filtered_english_words
            and len(base_word) > 3
        ):
            additional_words.append(base_word)

    # 원형 단어들 추가
    filtered_english_words.extend(additional_words)

    finded = []
    # 사전에서 영어 단어가 포함된 항목 찾기 (사전의 키 목록을 먼저 복사)
    # 동시성 문제 방지를 위해 사전의 키 목록을 미리 복사
    dict_keys = list(translation_dictionary.keys())

    for word in filtered_english_words:
        if len(word) > 3:  # 너무 짧은 단어는 제외
            for dict_key in dict_keys:
                if word.lower() in dict_key.lower().split():
                    if dict_key not in finded:
                        finded.append(dict_key)

    # finded가 비어있는 경우 처리
    if not finded:
        return {**state, "dictionary": dictionary}

    bm25 = BM25Okapi(
        [doc.lower().split() for doc in finded],
    )
    doc_scores = bm25.get_scores(
        [
            re.sub(r"'s$|s$", "", word)
            for word in re.sub(r"\[p[0-9]+\]", "", normalized_text).split(" ")
        ]
    )
    sorted_docs = sorted(enumerate(doc_scores), key=lambda x: x[1], reverse=True)

    # 점수가 0보다 큰 상위 항목 선택
    top_n_indices = [finded[i] for i, score in sorted_docs[:5] if score > 0]

    added = []
    for i in top_n_indices:
        if i not in added:
            added.append(i)
            if isinstance(translation_dictionary[i], list):
                dictionary.append(f"{i} -> {', '.join(translation_dictionary[i])}")
            else:
                dictionary.append(f"{i} -> {translation_dictionary[i]}")

    return {**state, "dictionary": dictionary}


async def translate_text(state):
    text_to_translate = state["replaced_text"]
    text_replaced_with_korean_dictionary = state["replaced_text"]
    llm: BaseChatModel = state["llm"]  # 항상 state에서 llm 가져오기
    context = state["context"]
    context.initialize_dictionaries()

    # llm이 없으면 오류 발생
    if llm is None:
        raise ValueError("LLM이 전달되지 않았습니다. state에 'llm' 키가 있어야 합니다.")

    try:
        dict_size = len(context.get_dictionary())
        logger.debug(f"초기 사전 크기: {dict_size}개 항목")
    except Exception as e:
        logger.warning(f"사전 크기 확인 중 오류: {e}")
        logger.debug("초기 사전 정보를 확인할 수 없습니다.")

    translation_dictionary = context.translation_dictionary
    translation_dictionary_lowercase = context.translation_dictionary_lowercase

    restored_text = text_to_translate

    # 플레이스홀더 복원
    for token, placeholder in state["placeholder_map"].items():
        restored_text = restored_text.replace(token, "")

    if restored_text.strip() == "":
        return {**state, "translated_text": text_to_translate}

    temp_placeholders = {}
    placeholder_idx = 1
    dictionary_entries = []

    # 동시성 문제 방지를 위해 사전의 키-값 쌍을 미리 복사
    dict_items = list(translation_dictionary.items())

    for key, item in dict_items:
        # 사전 항목 추가
        if len(key) >= 3:
            if key.lower() in text_replaced_with_korean_dictionary.lower():
                try:
                    dictionary_entries.append(
                        f"{key} -> {', '.join(item) if isinstance(item, list) else item}"
                    )
                except Exception as e:
                    logger.error(f"사전 항목 추가 중 오류 발생: {e} ({key}, {item})")
                    try:
                        dictionary_entries.append(f"{key} -> {item}")
                    except Exception as e:
                        pass
                temp_token = f"[TP{placeholder_idx}]"
                text_replaced_with_korean_dictionary = re.sub(
                    re.escape(key),
                    temp_token,
                    text_replaced_with_korean_dictionary,
                    flags=re.IGNORECASE,
                )
                temp_placeholders[temp_token] = item
                placeholder_idx += 1

    # state에서 가져온 dictionary를 복사하여 동시성 문제 방지
    orig_dictionary = state.get("dictionary", [])
    if orig_dictionary:
        orig_dictionary = list(orig_dictionary)  # 복사

    dictionary_items = {}

    for i in dictionary_entries:
        dictionary_items[i] = i
    for i in orig_dictionary:
        dictionary_items[i] = i

    if len(dictionary_items) > 0:
        dictionary_text = "\n".join(dictionary_items)
    else:
        dictionary_text = "No relevant dictionary entries found."

    has_placeholders = any(
        token.startswith("[P") for token in text_to_translate.split()
    )
    translation_rules = (
        RULES_FOR_PLACEHOLDER if has_placeholders else RULES_FOR_NO_PLACEHOLDER
    )
    placeholders_text = (
        "\n\n<placeholders>\n번역에 포함해야 할 플레이스홀더 목록입니다:\n"
        + "\n".join(state["placeholder_map"].keys())
        if has_placeholders
        else ""
    )

    translated_text = ""
    additional_rules = ""
    max_attempts = 10
    temperature = 0.1

    is_success = False
    for attempt in range(max_attempts):
        llm.temperature = temperature
        try:
            if llm is None:
                raise ValueError("LLM이 전달되지 않았습니다.")

            prompt_template = PromptTemplate(
                template=TEMPLATE_TRANSLATE_TEXT,
                input_variables=[
                    "text",
                    "dictionary",
                    "format_instructions",
                    "placeholders",
                    "additional_rules",
                    "dictionary_instructions",
                    "translation_rules",
                    "translation_key",
                ],
            )

            class CustomOutputParser(BaseOutputParser):
                """Custom boolean parser."""

                def parse(self, text: str) -> bool:
                    cleaned_text = text.replace("\\&", "&")
                    return cleaned_text

            class DictionaryEntry(BaseModel):
                en: str = Field(..., description="영어 단어")
                ko: str = Field(..., description="한글 단어")

            class TranslationResponse(BaseModel):
                translated_text: str = Field(
                    ...,
                    description="한글 번역 텍스트 (플레이스홀더 누락 금지)",
                )
                new_dictionary_entries: List[DictionaryEntry] = Field(
                    default_factory=list,
                    description="번역에 사용된 단어들 중, 사전에 추가할 새로운 단어들",
                )

            parser = PydanticOutputParser(pydantic_object=TranslationResponse)

            custom_parser = CustomOutputParser()
            chain = prompt_template | llm | custom_parser | parser

            try:
                # LLM 호출은 잠재적으로 오래 걸릴 수 있는 작업이므로 비동기로 처리
                result: TranslationResponse = await chain.ainvoke(
                    {
                        "text": text_to_translate,
                        "dictionary": dictionary_text,
                        "format_instructions": parser.get_format_instructions(),
                        "placeholders": placeholders_text,
                        "additional_rules": additional_rules,
                        "dictionary_instructions": DICTIONARY_INSTRUCTIONS,
                        "translation_rules": translation_rules,
                        "translation_key": state["translation_key"],
                    },
                )
            except Exception as api_error:
                raise RuntimeError(
                    f"API 호출 중 오류가 발생하여 번역이 중단되었습니다: {api_error}"
                )

            if (
                hasattr(result, "new_dictionary_entries")
                and result.new_dictionary_entries
            ):
                # 새 항목들을 임시 저장
                new_entries_to_add = []

                for entry in result.new_dictionary_entries:
                    if hasattr(entry, "en") and hasattr(entry, "ko"):
                        adding = False
                        # 동시성 문제 방지를 위해 현재 상태 확인
                        if entry.en.lower() not in translation_dictionary_lowercase:
                            adding = True
                        else:
                            target_key = translation_dictionary_lowercase[
                                entry.en.lower()
                            ]
                            target = translation_dictionary[target_key]
                            if isinstance(target, str):
                                if not re.match(r"[가-힣]+", target):
                                    adding = True
                            elif isinstance(target, list):
                                for t in target:
                                    if not re.match(r"[가-힣]+", t):
                                        adding = True
                                        break

                        if adding:
                            new_entries_to_add.append(
                                (entry.en.lower(), entry.ko.lower())
                            )

                # 모든 새 항목을 락을 통해 한번에 추가
                if new_entries_to_add:
                    for en_val, ko_val in new_entries_to_add:
                        await context.async_add_to_dictionary(en_val, ko_val)
                        logger.info(f"사전에 추가됨: {en_val} -> {ko_val}")

            translated_text = result.translated_text
            current_missing_placeholders = []
            for token in state["placeholder_map"].keys():
                if token not in translated_text:
                    current_missing_placeholders.append(token)

            pattern = r"\[P\d+\]"
            found_placeholders = re.findall(pattern, translated_text)
            extra_placeholders = [
                p
                for p in found_placeholders
                if p not in state["placeholder_map"].keys()
            ]

            if len(current_missing_placeholders) > 0 or len(extra_placeholders) > 0:
                logger.warning(
                    f"placeholder 문제가 발생했습니다: 누락={current_missing_placeholders}, 추가={extra_placeholders} / {translated_text} / {state['replaced_text']}"
                )

                emphasis = "###"
                new_additional_rules = f"\n\n{emphasis} 중요: 번역에서 placeholder 문제가 발생했습니다 (시도 {attempt + 1}/{max_attempts}) {emphasis}\n"

                if len(current_missing_placeholders) > 0:
                    new_additional_rules += "누락된 placeholder:\n"
                    for token in current_missing_placeholders:
                        new_additional_rules += f"- **{token}** 반드시 이 placeholder를 번역에 포함해야 합니다.\n"

                if len(extra_placeholders) > 0:
                    new_additional_rules += "원본에 없는 추가된 placeholder:\n"
                    for token in extra_placeholders:
                        new_additional_rules += f"- **{token}** 이 placeholder는 원본에 없습니다. 제거해야 합니다.\n"

                new_additional_rules += "\n이전 번역: " + translated_text + "\n"

                # 온도 조정
                temperature += 0.1
                additional_rules = new_additional_rules
                # 계속 다음 루프로 진행
            else:
                # 성공적으로 번역 완료
                is_success = True
                break

        except OutputParserException as e:
            temperature += 0.1
            additional_rules = "\n\n### 중요: json 형식을 지키지 않아 파싱 오류가 발생했습니다.\nformat_instructions을 반드시 지켜서 다시 작성 해주세요."
            logger.error(f"파싱 오류 발생: {e}, 프롬프트에 강조구문 추가 후 다시 시도")
        except RuntimeError as e:
            if "Invalid json output" in str(e):
                temperature += 0.1
                additional_rules = "\n\n### 중요: json 형식을 지키지 않아 파싱 오류가 발생했습니다.\nformat_instructions을 반드시 지켜서 다시 작성 해주세요."
                logger.error(
                    f"파싱 오류 발생: {e}, 프롬프트에 강조구문 추가 후 다시 시도"
                )
            else:
                logger.error(f"심각한 오류 발생으로 번역 중단: {e}")
                state["has_error"] = True
                return {**state, "translated_text": translated_text}
    if not is_success:
        logger.error(f"모든 시도 후에도 번역 실패: {translated_text}")
        state["has_error"] = True
        return {**state, "translated_text": translated_text}
    # 모든 시도 후에도 플레이스홀더 문제가 있다면 경고 로그 남김
    missing_placeholders = []
    if has_placeholders:
        for token in state["placeholder_map"].keys():
            if token not in translated_text:
                missing_placeholders.append(token)

    if missing_placeholders:
        logger.error(f"최종 번역에 플레이스홀더가 누락됨: {missing_placeholders}")

    return {**state, "translated_text": translated_text}


# 특수 형식 복원
async def restore_formats(state):
    restored_text = restore_special_formats(
        state["translated_text"],
        state["placeholder_map"],
    )
    return {**state, "restored_text": restored_text}


def create_translation_graph():
    # 상태 스키마 정의
    from typing import TypedDict

    class TranslationState(TypedDict):
        text: str
        replaced_text: str
        custom_dictionary_dict: dict
        placeholder_map: dict
        has_error: bool
        dictionary: list
        translated_text: str
        llm: BaseChatModel
        restored_text: str
        context: TranslationContext
        translation_key: str

    # 워크플로우 그래프 정의
    workflow = StateGraph(TranslationState)

    # 노드 추가 (비동기 함수로 변환됨)
    workflow.add_node("analyze", analyze_text)
    workflow.add_node("retrieve", retrieve_translations)
    workflow.add_node("translate", translate_text)
    workflow.add_node("restore", restore_formats)

    # 엣지 연결
    workflow.add_edge("analyze", "retrieve")
    workflow.add_edge("retrieve", "translate")
    workflow.add_edge("translate", "restore")
    workflow.add_edge("restore", END)

    workflow.set_entry_point("analyze")

    # 그래프 컴파일 및 반환
    graph = workflow.compile()
    return graph


async def translate_item(
    input_path: str,
    key: str,
    value: Any,
    context: TranslationContext,
    llm: BaseChatModel = None,
    progress_callback=None,
    delay_manager: DelayManager = None,
) -> Any:
    """한 항목을 비동기적으로 번역합니다."""
    try:
        # API 요청 전 딜레이 적용
        if delay_manager:
            await delay_manager.wait_before_request()

        translated_value, has_error = await registry.aprocess_item(
            input_path, key, value, context, llm
        )

        # API 요청 후 딜레이 적용
        if delay_manager:
            await delay_manager.wait_after_request()

        if progress_callback:
            await progress_callback()
        return key, translated_value, has_error
    except RuntimeError as e:
        # API 할당량 초과나 심각한 LLM 오류 발생 시
        logger.error(f"LLM API 오류로 번역이 중단되었습니다: {e}")
        raise
    except Exception as e:
        logger.error(f"항목 '{key}' 번역 중 오류 발생: {e}")
        logger.info(traceback.format_exc())
        # 일반 오류는 원본 값 반환
        return key, value


async def translate_json_file(
    input_path: str,
    output_path: str,
    ko_data: dict = {},
    custom_dictionary_dict: Dict = {},
    llm=None,
    max_workers: int = 5,
    progress_callback=None,
    external_context=None,
    delay_manager: DelayManager = None,
    use_random_order: bool = False,
    force_keep_line_break: bool = False,
):
    """
    JSON 파일을 비동기적으로 번역합니다.

    Parameters:
        input_path: 번역할 JSON 파일 경로
        output_path: 번역 결과를 저장할 경로
        custom_dictionary_dict: 사용자 정의 사전
        llm: 번역에 사용할 언어 모델 인스턴스 (필수)
        max_workers: 동시 작업자 수
        progress_callback: 진행 상황 콜백 함수
        external_context: 외부에서 제공하는 TranslationContext 객체
        delay_manager: API 요청 사이 딜레이를 관리하는 객체
    """
    # llm이 제공되지 않은 경우 오류 발생
    if llm is None:
        raise ValueError(
            "llm은 필수 인자입니다. 번역을 위해 언어 모델을 제공해야 합니다."
        )

    # 딜레이 관리자가 없으면 기본값으로 생성
    if delay_manager is None:
        delay_manager = DelayManager(delay=0)
        logger.info("딜레이 관리자가 제공되지 않아 기본 딜레이 0초로 설정합니다.")

    # 입력 JSON 파일 로드
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 번역 그래프 생성
    translation_graph = create_translation_graph()

    # 번역 결과를 저장할 복사본 생성
    translated_data = ko_data

    # 진행 상황 표시
    logger.info(f"총 {len(data)}개 항목 번역 시작...")

    # 컨텍스트 생성 또는 외부에서 전달된 컨텍스트 사용
    if external_context:
        context = external_context
        logger.info("외부에서 제공된 컨텍스트를 사용합니다.")
    else:
        # 공유 컨텍스트 생성 (모든 워커가 이 컨텍스트를 공유함)
        context = TranslationContext(
            translation_graph=translation_graph,
            custom_dictionary_dict=custom_dictionary_dict,
            registry=registry,
            force_keep_line_break=force_keep_line_break,
        )

    # 공유 사전 초기화
    context.initialize_dictionaries()

    try:
        dict_size = len(context.get_dictionary())
        logger.info(f"초기 사전 크기: {dict_size}개 항목")
    except Exception as e:
        logger.warning(f"사전 크기 확인 중 오류: {e}")
        logger.info("초기 사전 정보를 확인할 수 없습니다.")

    # 작업 큐 생성
    queue = asyncio.Queue()

    # 큐에 작업 추가 (랜덤 순서로)
    items = list(data.items())
    if use_random_order:
        random.shuffle(items)  # 리스트 순서 섞기
    for key, value in items:
        await queue.put((key, value))

    # 공유 사전 상태 저장용 락
    dict_save_lock = asyncio.Lock()
    last_save_size = len(context.get_dictionary())

    error_list = []

    # Worker 함수 정의
    async def worker(worker_id: int):
        nonlocal last_save_size, error_list

        while not queue.empty():
            try:
                key, value = await queue.get()

                if translated_data.get(key, None) is None:
                    logger.warning(f"한글 공식 번역 존재로 번역 건너뜀: {key}")
                    continue

                key, translated_value, has_error = await translate_item(
                    input_path,
                    key,
                    value,
                    context,
                    llm,
                    progress_callback,
                    delay_manager,
                )
                if not has_error:
                    translated_data[key] = translated_value
                else:
                    error_list.append((input_path, key, value, translated_value))
                # 사전 크기 확인 및 중간 저장 (사전 항목이 10개 이상 추가되면)
                current_dict_size = len(context.get_dictionary())
                if current_dict_size - last_save_size >= 100:
                    async with dict_save_lock:
                        # 다른 워커가 이미 저장했는지 다시 확인
                        if current_dict_size - last_save_size >= 100:
                            try:
                                # 중간 결과 파일 저장
                                with open(output_path, "w", encoding="utf-8") as f:
                                    json.dump(
                                        translated_data, f, ensure_ascii=False, indent=4
                                    )

                                last_save_size = current_dict_size
                                logger.info(
                                    f"중간 사전 저장 완료: {current_dict_size}개 항목"
                                )
                            except Exception as save_error:
                                logger.error(
                                    f"중간 결과 저장 중 오류 발생: {save_error}"
                                )

            except Exception as e:
                logger.error(f"Worker {worker_id} 오류: {e}")
            finally:
                queue.task_done()

    # Worker 시작
    workers = []
    for i in range(max_workers):
        task = asyncio.create_task(worker(i))
        workers.append(task)

    # 모든 작업이 완료될 때까지 대기
    await queue.join()

    # Worker 태스크 취소
    for task in workers:
        task.cancel()

    # 완료된 태스크 처리
    await asyncio.gather(*workers, return_exceptions=True)

    # 번역된 데이터 저장
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(translated_data, f, ensure_ascii=False, indent=4)
        logger.info(f"번역 완료. 결과가 {output_path}에 저장되었습니다.")
    except Exception as save_error:
        logger.error(f"최종 결과 저장 중 오류 발생: {save_error}")
        # 대체 경로에 저장 시도
        try:
            backup_path = f"{output_path}.backup.json"
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(translated_data, f, ensure_ascii=False, indent=4)
            logger.info(f"백업 결과가 {backup_path}에 저장되었습니다.")
        except Exception as backup_save_error:
            logger.error(f"백업 저장 중 오류 발생: {backup_save_error}")

    # 최종 번역 사전 반환
    return context.get_dictionary()
