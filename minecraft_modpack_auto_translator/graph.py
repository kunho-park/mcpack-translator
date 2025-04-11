import asyncio
import copy
import json
import logging
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
from .loaders import (
    DefaultLoader,
    DictLoader,
    FTBQuestsChapterQuestsLoader,
    FTBQuestsChapterTitleLoader,
    ListLoader,
    LoaderRegistry,
    PatchouliBooksLoader,
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
    context = state.get("context")
    if context:
        context.initialize_dictionaries()

    return {
        "text": text,
        "replaced_text": replaced_text,
        "placeholder_map": placeholder_map,
        "extracted_entities": [],
        "context": context,
    }


# RAG에서 번역 정보 검색
async def retrieve_translations(state):
    context = state["context"]
    context.initialize_dictionaries()
    translation_dictionary = context.translation_dictionary

    dictionary = []
    text = state["replaced_text"]
    normalized_text = text.lower()

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
    # 사전에서 영어 단어가 포함된 항목 찾기
    for word in filtered_english_words:
        if len(word) > 3:  # 너무 짧은 단어는 제외
            for dict_key in translation_dictionary.keys():
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
    top_n_indices = [finded[i] for i, score in sorted_docs[:8] if score > 0]

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
    llm: BaseChatModel = state["llm"]
    context = state["context"]
    context.initialize_dictionaries()
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

    for key, item in translation_dictionary.items():
        # 사전 항목 추가
        if len(key) > 3:
            if key.lower() in text_replaced_with_korean_dictionary.lower():
                dictionary_entries.append(
                    f"{key} -> {', '.join(item) if isinstance(item, list) else item}"
                )
                temp_token = f"[TP{placeholder_idx}]"
                text_replaced_with_korean_dictionary = re.sub(
                    re.escape(key),
                    temp_token,
                    text_replaced_with_korean_dictionary,
                    flags=re.IGNORECASE,
                )
                temp_placeholders[temp_token] = item
                placeholder_idx += 1

    dictionary_items = set(state.get("dictionary", []) + dictionary_entries)
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
                ],
            )

            class CustomOutputParser(BaseOutputParser):
                """Custom boolean parser."""

                def parse(self, text: str) -> bool:
                    pattern = r'\\([^"\\/bfnrtu])'
                    cleaned_text = re.sub(pattern, lambda m: f"\\\\{m.group(1)}", text)
                    return cleaned_text

            class DictionaryEntry(BaseModel):
                en: str = Field(..., description="English word")
                ko: str = Field(..., description="Translated word")

            class TranslationResponse(BaseModel):
                translated_text: str = Field(
                    ...,
                    description="Korean translated text (do not miss placeholders)",
                )
                new_dictionary_entries: List[DictionaryEntry] = Field(
                    default_factory=list,
                    description="New dictionary entries to add to the dictionary",
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
                for entry in result.new_dictionary_entries:
                    if hasattr(entry, "en") and hasattr(entry, "ko"):
                        adding = False
                        if entry.en.lower() not in translation_dictionary_lowercase:
                            adding = True
                        else:
                            target = translation_dictionary[
                                translation_dictionary_lowercase[entry.en.lower()]
                            ]
                            if isinstance(target, str):
                                if not re.match(r"[가-힣]+", target):
                                    adding = True
                            elif isinstance(target, list):
                                for t in target:
                                    if not re.match(r"[가-힣]+", t):
                                        adding = True
                                        break

                        if adding:
                            context.add_to_dictionary(
                                entry.en.lower(), entry.ko.lower()
                            )
                            logger.info(
                                f"사전에 추가됨: {entry.en.lower()} -> {entry.ko.lower()}"
                            )

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
                break

        except OutputParserException as e:
            temperature += 0.1
            additional_rules = "\n\n### 중요: json 형식을 지키지 않아 파싱 오류가 발생했습니다.\nformat_instructions을 반드시 지켜서 다시 작성 해주세요."
            logger.error(f"파싱 오류 발생: {e}, 프롬프트에 강조구문 추가 후 다시 시도")
        except RuntimeError as e:
            # RuntimeError는 번역을 계속할 수 없는 심각한 오류이므로 바로 예외 던지기
            logger.error(f"심각한 오류 발생으로 번역 중단: {e}")
            raise

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
    from typing import NotRequired, TypedDict

    class TranslationState(TypedDict):
        text: str
        replaced_text: str
        custom_dictionary_dict: dict
        placeholder_map: dict
        dictionary: NotRequired[list]
        translated_text: NotRequired[str]
        llm: NotRequired[BaseChatModel]
        restored_text: NotRequired[str]
        context: NotRequired[TranslationContext]

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
    progress_callback=None,
) -> Any:
    """한 항목을 비동기적으로 번역합니다."""
    try:
        translated_value = await registry.aprocess_item(input_path, key, value, context)
        if progress_callback:
            await progress_callback()
        return key, translated_value
    except RuntimeError as e:
        # API 할당량 초과나 심각한 LLM 오류 발생 시
        logger.error(f"LLM API 오류로 번역이 중단되었습니다: {e}")
        raise
    except Exception as e:
        logger.error(f"항목 '{key}' 번역 중 오류 발생: {e}")
        logger.debug(traceback.format_exc())
        # 일반 오류는 원본 값 반환
        return key, value


async def translate_json_file(
    input_path: str,
    output_path: str,
    custom_dictionary_dict: Dict = {},
    llm=None,
    max_workers: int = 5,
    progress_callback=None,
):
    """JSON 파일을 비동기적으로 번역합니다."""
    # 입력 JSON 파일 로드
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 번역 그래프 생성
    translation_graph = create_translation_graph()

    # 번역 결과를 저장할 복사본 생성
    translated_data = copy.deepcopy(data)

    # 진행 상황 표시
    logger.info(f"총 {len(data)}개 항목 번역 시작...")

    # 컨텍스트 생성
    context = TranslationContext(
        translation_graph=translation_graph,
        custom_dictionary_dict=custom_dictionary_dict,
        llm=llm,
        registry=registry,
    )

    # 작업 큐 생성
    queue = asyncio.Queue()

    # 큐에 작업 추가
    for key, value in data.items():
        await queue.put((key, value))

    # Worker 함수 정의
    async def worker(worker_id: int):
        while not queue.empty():
            try:
                key, value = await queue.get()
                key, translated_value = await translate_item(
                    input_path, key, value, context, progress_callback
                )
                translated_data[key] = translated_value
                queue.task_done()

                # 주기적으로 중간 결과 저장 (100개 항목마다)
                if queue.qsize() % 100 == 0:
                    try:
                        with open(output_path, "w", encoding="utf-8") as f:
                            json.dump(translated_data, f, ensure_ascii=False, indent=4)
                    except Exception as save_error:
                        logger.error(f"중간 결과 저장 중 오류 발생: {save_error}")

            except Exception as e:
                logger.error(f"Worker {worker_id} 오류: {e}")
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
