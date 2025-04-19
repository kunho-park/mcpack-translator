import asyncio
import json
import logging
import os
import re
import shutil
import sys
import time
import traceback
import uuid
import zipfile
from glob import escape as glob_escape
from glob import glob

import streamlit as st
from langchain_core.rate_limiters import InMemoryRateLimiter

# Windows 환경에서 asyncio 이벤트 루프 정책 설정
if sys.platform.startswith("win"):
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import minecraft_modpack_auto_translator
from minecraft_modpack_auto_translator import create_resourcepack
from minecraft_modpack_auto_translator.config import (
    DICTIONARY_PREFIX_WHITELIST,
    DICTIONARY_SUFFIX_BLACKLIST,
    DIR_FILTER_WHITELIST,
    OFFICIAL_EN_LANG_FILE,
    OFFICIAL_KO_LANG_FILE,
)
from minecraft_modpack_auto_translator.delay_manager import DelayManager
from minecraft_modpack_auto_translator.graph import (
    create_translation_graph,
    registry,
)
from minecraft_modpack_auto_translator.loaders.context import (
    TranslationContext,
)
from minecraft_modpack_auto_translator.translator import get_translator

st.set_page_config(
    page_title="마인크래프트 모드팩 자동 번역기", page_icon="🎮", layout="wide"
)

logger = logging.getLogger(__name__)
# 디버그 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# 언어 코드 설정
# .env 파일에서 언어 코드를 가져옵니다. 기본값은 "ko_kr"입니다.
LANG_CODE = os.getenv("LANG_CODE", "ko_kr")

# API 키 환경 변수 이름 매핑
API_KEY_ENV_VARS = {
    "OpenAI": "OPENAI_API_KEY",
    "Google": "GOOGLE_API_KEY",
    "Grok": "GROK_API_KEY",
    "Ollama": "OLLAMA_API_KEY",
    "Anthropic": "ANTHROPIC_API_KEY",
}

# API 베이스 URL 환경 변수 이름 매핑
API_BASE_ENV_VARS = {
    "OpenAI": "OPENAI_API_BASE",
    "Google": "GOOGLE_API_BASE",
    "Grok": "GROK_API_BASE",
    "Ollama": "OLLAMA_API_BASE",
    "Anthropic": "ANTHROPIC_API_BASE",
}


def get_supported_extensions():
    """지원하는 파일 확장자 목록을 반환합니다."""
    from minecraft_modpack_auto_translator.parsers.base_parser import BaseParser

    return BaseParser.get_supported_extensions()


def get_parser_by_extension(extension):
    """파일 확장자에 맞는 파서 클래스를 반환합니다."""
    from minecraft_modpack_auto_translator.parsers.base_parser import BaseParser

    return BaseParser.get_parser_by_extension(extension)


def add_to_dictionary(
    en_value, ko_value, translation_dictionary, translation_dictionary_lowercase
):
    try:
        if en_value.lower() in translation_dictionary_lowercase:
            target = translation_dictionary[
                translation_dictionary_lowercase[en_value.lower()]
            ]
            if isinstance(target, list):
                if ko_value not in target:
                    translation_dictionary[
                        translation_dictionary_lowercase[en_value.lower()]
                    ].append(ko_value)
            elif isinstance(target, str):
                if (
                    translation_dictionary[
                        translation_dictionary_lowercase[en_value.lower()]
                    ]
                    != ko_value
                ):
                    translation_dictionary[
                        translation_dictionary_lowercase[en_value.lower()]
                    ] = [
                        translation_dictionary[
                            translation_dictionary_lowercase[en_value.lower()]
                        ],
                        ko_value,
                    ]
            else:
                st.error(
                    f"translation_dictionary[{en_value.lower()}]의 타입이 예상과 다릅니다: {type(translation_dictionary[en_value.lower()])}"
                )
        else:
            translation_dictionary[en_value] = ko_value
            translation_dictionary_lowercase[en_value.lower()] = en_value

        return translation_dictionary, translation_dictionary_lowercase
    except Exception:
        logger.error(f"번역 사전 추가 중 오류: {en_value}, {ko_value}")
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        return translation_dictionary, translation_dictionary_lowercase


def build_dictionary_from_files(
    en_us_files,
    modpack_path,
    translation_dictionary,
    translation_dictionary_lowercase,
    source_lang_code,
):
    """주어진 원본 언어 파일과 해당하는 목표 언어 파일에서 번역 사전을 구축합니다."""

    file_count = 0
    entries_added = 0

    for en_file in en_us_files:
        try:
            # 목표 언어 파일 경로 추정
            rel_path = en_file.replace(modpack_path, "").lstrip("/\\")
            target_lang_file = os.path.join(
                modpack_path,
                rel_path.replace(source_lang_code, LANG_CODE, 1),  # 첫 번째 발생만 교체
            )

            # 목표 언어 파일이 존재하는 경우
            if os.path.exists(target_lang_file):
                # 파일 내용 로드
                en_data = extract_lang_content(en_file)
                ko_data = extract_lang_content(
                    target_lang_file
                )  # 변수명은 ko_data 유지

                if not isinstance(en_data, dict) or not isinstance(ko_data, dict):
                    continue

                # 번역 사전에 추가
                for key, en_value in en_data.items():
                    if (
                        key in ko_data
                        and isinstance(en_value, str)
                        and isinstance(ko_data[key], str)
                    ):
                        ko_value = ko_data[key]

                        # 동일한 값이면 건너뛰기
                        if en_value == ko_value:
                            continue

                        # 화이트리스트/블랙리스트 필터링
                        if (
                            key.split(".")[0] in DICTIONARY_PREFIX_WHITELIST
                            and key.split(".")[-1] not in DICTIONARY_SUFFIX_BLACKLIST
                        ):
                            # 언더스코어 제거
                            clean_en = en_value.replace("_", "")
                            clean_ko = ko_value.replace("_", "")

                            translation_dictionary, translation_dictionary_lowercase = (
                                add_to_dictionary(
                                    clean_en,
                                    clean_ko,
                                    translation_dictionary,
                                    translation_dictionary_lowercase,
                                )
                            )
                            entries_added += 1

                file_count += 1

        except Exception as e:
            error_traceback = traceback.format_exc()
            st.error(
                f"파일 처리 중 오류: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
            )
            logger.error(error_traceback)

    return (
        translation_dictionary,
        translation_dictionary_lowercase,
        file_count,
        entries_added,
    )


def build_dictionary_from_jar(
    jar_files,
    translation_dictionary,
    translation_dictionary_lowercase,
    source_lang_code,
):
    """JAR 파일 내부의 언어 파일에서 번역 사전을 구축합니다."""

    file_count = 0
    entries_added = 0
    supported_extensions = get_supported_extensions()

    for jar_path in jar_files:
        try:
            with zipfile.ZipFile(jar_path, "r") as jar:
                # 원본 언어 파일 찾기
                source_lang_files = [
                    f
                    for f in jar.namelist()
                    if os.path.splitext(f)[1] in supported_extensions
                    and (
                        source_lang_code.lower() in f.lower()
                    )  # 사용자가 입력한 언어 코드 사용
                ]

                for en_file in source_lang_files:
                    # 목표 언어 파일 경로 추정
                    target_lang_file = en_file.replace(
                        source_lang_code, LANG_CODE, 1
                    )  # 첫 번째 발생만 교체

                    # 두 파일이 모두 존재하는 경우
                    if target_lang_file in jar.namelist():
                        try:
                            # 파일 내용 로드
                            with jar.open(en_file, "r") as f:
                                file_bytes = f.read()
                                en_content = file_bytes.decode("utf-8", errors="ignore")

                            with jar.open(
                                target_lang_file, "r"
                            ) as f:  # 변수명은 ko_content 유지
                                file_bytes = f.read()
                                ko_content = file_bytes.decode("utf-8", errors="ignore")

                            # 파서로 파싱
                            file_ext = os.path.splitext(en_file)[1]
                            parser_class = get_parser_by_extension(file_ext)

                            if parser_class:
                                en_data = parser_class.load(en_content)
                                ko_data = parser_class.load(ko_content)

                                # 번역 사전에 추가
                                for key, en_value in en_data.items():
                                    if (
                                        key in ko_data
                                        and isinstance(en_value, str)
                                        and isinstance(ko_data[key], str)
                                    ):
                                        ko_value = ko_data[key]

                                        # 동일한 값이면 건너뛰기
                                        if en_value == ko_value:
                                            continue

                                        # 화이트리스트/블랙리스트 필터링
                                        if (
                                            key.split(".")[0]
                                            in DICTIONARY_PREFIX_WHITELIST
                                            and key.split(".")[-1]
                                            not in DICTIONARY_SUFFIX_BLACKLIST
                                        ):
                                            # 언더스코어 제거
                                            clean_en = en_value.replace("_", "")
                                            clean_ko = ko_value.replace("_", "")

                                            (
                                                translation_dictionary,
                                                translation_dictionary_lowercase,
                                            ) = add_to_dictionary(
                                                clean_en,
                                                clean_ko,
                                                translation_dictionary,
                                                translation_dictionary_lowercase,
                                            )
                                            entries_added += 1

                                file_count += 1

                        except Exception as e:
                            st.error(
                                f"JAR 파일 내부 파일 처리 중 오류: {jar_path}, {en_file}, {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
                            )
                            error_traceback = traceback.format_exc()
                            logger.error(error_traceback)

        except Exception as e:
            st.error(
                f"JAR 파일 처리 중 오류: {jar_path}, {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
            )
            error_traceback = traceback.format_exc()
            logger.error(error_traceback)

    return (
        translation_dictionary,
        translation_dictionary_lowercase,
        file_count,
        entries_added,
    )


def normalize_glob_path(path):
    """glob 패턴에서 사용할 경로를 정규화합니다."""
    normalized = path.replace("\\", "/")
    parts = []

    for part in normalized.split("/"):
        if part.startswith("**"):
            parts.append(part)
        elif part.startswith("*"):
            parts.append(part)
        else:
            parts.append(glob_escape(part))
    return "/".join(parts)


def process_modpack_directory(
    modpack_path,
    source_lang_code,
    translate_config=True,
    translate_kubejs=True,
    translate_mods=True,
):
    """모드팩 디렉토리에서 번역 대상 파일을 찾습니다."""
    supported_extensions = get_supported_extensions()
    source_lang_code_lower = source_lang_code.lower()  # 소문자로 변환하여 사용

    # 번역 대상 파일 검색
    source_lang_files = []

    # config 폴더 내 파일 검색 (선택한 경우)
    if translate_config:
        config_glob_path = normalize_glob_path(
            os.path.join(modpack_path, "config/**/*.*")
        )
        config_files = glob(config_glob_path, recursive=True)
        for f in config_files:
            f = f.replace("\\", "/")
            file_ext = os.path.splitext(f)[1]
            if file_ext in supported_extensions and any(
                whitelist_dir in f for whitelist_dir in DIR_FILTER_WHITELIST
            ):
                source_lang_files.append(f)
            elif file_ext in supported_extensions and (
                source_lang_code_lower in f.lower()
            ):  # 사용자 입력 언어 코드 확인
                source_lang_files.append(f)

    # kubejs 폴더 내 파일 검색 (선택한 경우)
    if translate_kubejs:
        kubejs_glob_path = normalize_glob_path(
            os.path.join(modpack_path, "kubejs/**/*.*")
        )
        kubejs_files = glob(kubejs_glob_path, recursive=True)
        for f in kubejs_files:
            f = f.replace("\\", "/")
            file_ext = os.path.splitext(f)[1]
            if file_ext in supported_extensions and any(
                whitelist_dir in f for whitelist_dir in DIR_FILTER_WHITELIST
            ):
                source_lang_files.append(f)
            elif file_ext in supported_extensions and (
                source_lang_code_lower in f.lower()
            ):  # 사용자 입력 언어 코드 확인
                source_lang_files.append(f)

    # mods 폴더 내 jar 파일 검색 (선택한 경우)
    mods_jar_files = []
    if translate_mods:
        mods_glob_path = normalize_glob_path(os.path.join(modpack_path, "mods/*.jar"))
        mods_jar_files = glob(mods_glob_path)

        extract_dir = os.path.join(modpack_path, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        for jar_path in mods_jar_files:
            try:
                with zipfile.ZipFile(jar_path, "r") as jar:
                    # 지원하는 파일 형식 찾기
                    lang_files = [
                        f
                        for f in jar.namelist()
                        if os.path.splitext(f)[1] in supported_extensions
                        and (
                            any(
                                whitelist_dir in f
                                for whitelist_dir in DIR_FILTER_WHITELIST
                            )
                            or (
                                source_lang_code_lower in f.lower()
                            )  # 사용자 입력 언어 코드 확인
                        )
                    ]

                    for lang_file in lang_files:
                        # 임시 디렉토리에 파일 추출
                        extract_path = os.path.join(
                            extract_dir, os.path.basename(jar_path), lang_file
                        ).replace("\\", "/")
                        os.makedirs(os.path.dirname(extract_path), exist_ok=True)

                        with (
                            jar.open(lang_file) as source,
                            open(extract_path, "wb") as target,
                        ):
                            shutil.copyfileobj(source, target)

                        source_lang_files.append(extract_path)
            except Exception as e:
                st.error(
                    f"JAR 파일 처리 중 오류: {e}, {jar_path}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
                )
                error_traceback = traceback.format_exc()
                logger.error(error_traceback)

    return source_lang_files, mods_jar_files


def extract_lang_content(file_path):
    """파일에서 언어 내용을 추출합니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        file_ext = os.path.splitext(file_path)[1]
        parser_class = get_parser_by_extension(file_ext)

        if parser_class:
            return parser_class.load(content)
        else:
            st.error(f"지원되지 않는 파일 형식: {file_ext}")
            return {}
    except Exception as e:
        st.error(
            f"파일 내용 추출 중 오류: {file_path}, {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
        )
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        return {}


def save_lang_content(file_path, data):
    """언어 내용을 파일에 저장합니다."""
    try:
        file_ext = os.path.splitext(file_path)[1]
        parser_class = get_parser_by_extension(file_ext)

        if parser_class:
            content = parser_class.save(data)

            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return True
        else:
            st.error(f"지원되지 않는 파일 형식: {file_ext}")
            return False
    except Exception as e:
        st.error(
            f"파일 저장 중 오류: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
        )
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        return False


def main():
    st.title("마인크래프트 모드팩 자동 번역기")

    # 글로벌 API 키 인덱스 상태 변수 초기화
    if "api_key_index" not in st.session_state:
        st.session_state.api_key_index = 0

    # 사이드바에 모델 선택 옵션
    st.sidebar.header("번역 설정")

    # LLM 모델 선택
    model_provider = st.sidebar.selectbox(
        "AI 모델 제공자 선택", ["OpenAI", "Google", "Grok", "Ollama", "Anthropic"]
    )

    # 모델 제공자에 따른 키와 모델 입력 필드
    env_api_key = os.getenv(API_KEY_ENV_VARS.get(model_provider, ""))

    # API 키 저장소 키
    api_keys_key = f"{model_provider}_api_keys"

    # API 키 관리 섹션
    st.sidebar.subheader("API 키 관리")

    # 세션 상태에 API 키 저장
    if api_keys_key not in st.session_state:
        st.session_state[api_keys_key] = env_api_key if env_api_key else ""

    # API 키 텍스트 영역 (여러 줄 입력 가능)
    api_keys_text = st.sidebar.text_area(
        f"{model_provider} API 키 목록 (한 줄에 하나씩)",
        value=st.session_state[api_keys_key],
        placeholder="여러 API 키를 한 줄에 하나씩 입력하세요.\n번역 시 위에서부터 순서대로 사용됩니다.",
        height=150,
        key=f"{model_provider}_api_keys_input",
    )

    # 입력된 API 키를 세션 상태에 저장
    st.session_state[api_keys_key] = api_keys_text

    # API 키 목록 처리
    api_keys = [key.strip() for key in api_keys_text.split("\n") if key.strip()]

    # API 키 가져오기/내보내기 버튼
    api_keys_col1, api_keys_col2 = st.sidebar.columns(2)

    with api_keys_col1:
        if st.button("API 키 내보내기", key=f"{model_provider}_export_button"):
            if api_keys:
                # API 키를 JSON으로 변환
                api_keys_json = json.dumps(
                    {model_provider: api_keys}, ensure_ascii=False, indent=2
                )
                # 다운로드 링크 생성
                st.download_button(
                    label="JSON 파일 다운로드",
                    data=api_keys_json,
                    file_name=f"{model_provider.lower()}_api_keys.json",
                    mime="application/json",
                    key=f"{model_provider}_download_button",
                )
            else:
                st.sidebar.warning("내보낼 API 키가 없습니다.")

    with api_keys_col2:
        api_keys_file = st.file_uploader(
            "API 키 가져오기", type=["json"], key=f"{model_provider}_import_file"
        )

        # 파일 처리 상태를 저장할 session_state 키
        processed_flag_key = f"{model_provider}_api_keys_file_processed"
        # 현재 업로드된 파일 ID 저장 키 (선택 사항, 파일 변경 감지용)
        current_file_id_key = f"{model_provider}_api_keys_file_id"

        # session_state 초기화
        if processed_flag_key not in st.session_state:
            st.session_state[processed_flag_key] = False
        if current_file_id_key not in st.session_state:
            st.session_state[current_file_id_key] = None

        if api_keys_file is not None:
            # 현재 파일 ID 가져오기 -> 파일 이름과 크기로 변경
            current_file_identifier = (api_keys_file.name, api_keys_file.size)

            # 새 파일이 업로드되었거나 아직 처리되지 않은 경우
            if (
                not st.session_state[processed_flag_key]
                or st.session_state[current_file_id_key] != current_file_identifier
            ):
                try:
                    api_keys_data = json.load(api_keys_file)
                    if model_provider in api_keys_data and isinstance(
                        api_keys_data[model_provider], list
                    ):
                        # 기존 텍스트 영역 값을 새로운 API 키로 업데이트
                        new_keys_text = "\n".join(api_keys_data[model_provider])
                        st.session_state[api_keys_key] = new_keys_text

                        # 처리 완료 상태 및 파일 ID 저장 -> 파일 식별자로 변경
                        st.session_state[processed_flag_key] = True
                        st.session_state[current_file_id_key] = current_file_identifier

                        st.sidebar.success(
                            f"{len(api_keys_data[model_provider])}개의 API 키를 가져왔습니다."
                        )
                        # 성공 메시지 후 rerun하여 text_area 업데이트 반영
                        st.rerun()
                    else:
                        st.sidebar.warning(
                            f"JSON 파일에 {model_provider} API 키가 없습니다."
                        )
                        # 오류 발생 시 처리 상태 초기화
                        st.session_state[processed_flag_key] = False
                        st.session_state[current_file_id_key] = None

                except Exception as e:
                    st.sidebar.error(f"JSON 파일 로드 오류: {str(e)}")
                    # 오류 발생 시 처리 상태 초기화
                    st.session_state[processed_flag_key] = False
                    st.session_state[current_file_id_key] = None
        else:
            # 파일이 제거되면 처리 상태 초기화
            if st.session_state[processed_flag_key]:
                st.session_state[processed_flag_key] = False
                st.session_state[current_file_id_key] = None
                # 상태 초기화 후 rerun하여 UI 반영
                st.rerun()

    model_options = {
        "OpenAI": [
            "gpt-4.5-preview",
            "gpt-4o",
            "gpt-4o-mini",
        ],
        "Google": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
        ],
        "Grok": ["grok-2-1212"],
        "Ollama": ["직접 입력 하세요."],
        "Anthropic": [
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
        ],
    }

    # 모델 선택 (드롭다운 또는 직접 입력)
    use_custom_model = st.sidebar.checkbox("직접 모델명 입력하기")

    if use_custom_model:
        selected_model = st.sidebar.text_input("모델명 직접 입력")
    else:
        selected_model = st.sidebar.selectbox(
            "모델 선택", model_options.get(model_provider, [])
        )

    # API Base URL (환경 변수에서 먼저 읽기)
    env_api_base = os.getenv(API_BASE_ENV_VARS.get(model_provider, ""))
    default_api_base = "http://localhost:11434" if model_provider == "Ollama" else ""

    # API Base URL 수정 여부 체크박스
    use_custom_api_base = st.sidebar.checkbox("API Base URL 수정하기")

    if use_custom_api_base:
        api_base_url = st.sidebar.text_input(
            "API Base URL", value=env_api_base if env_api_base else default_api_base
        )
    else:
        api_base_url = None

    # 모델 온도(temperature) 설정 - 모든 모델에 공통 적용
    temperature = st.sidebar.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=0.0,
        step=0.05,
        help="값이 낮을수록 더 창의성이 낮은 응답이, 높을수록 더 창의성이 높은 응답이 생성됩니다. 각 모델별로 제공사(Google, OpenAI)가 추천하는 값이 다름으로 공식 문서를 참고하여 설정하세요.",
    )

    # API 속도 제한 설정
    st.sidebar.subheader("API 속도 제한")
    use_rate_limiter = st.sidebar.checkbox("API 속도 제한 사용", value=True)
    rpm = st.sidebar.number_input(
        "분당 요청 수(RPM)",
        min_value=1,
        max_value=1000,
        value=60,
        step=1,
        disabled=not use_rate_limiter,
        help="분당 최대 API 요청 횟수를 설정합니다. 값이 낮을수록 API 할당량을 절약할 수 있습니다.",
    )

    st.sidebar.subheader("요청 딜레이 설정")
    use_request_delay = st.sidebar.checkbox("요청 사이 딜레이 사용", value=False)
    request_delay = st.sidebar.number_input(
        "요청 간 딜레이(초)",
        min_value=0.0,
        max_value=10.0,
        value=0.5,
        step=0.1,
        format="%.1f",
        disabled=not use_request_delay,
        help="각 API 요청 사이의 최소 대기 시간을 설정합니다. 값이 높을수록 API 오류가 감소할 수 있지만 번역 속도가 느려집니다.",
    )

    # 병렬 처리 설정
    st.sidebar.subheader("병렬 처리 설정")
    max_workers = st.sidebar.number_input(
        "동시 작업자 수",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
        help="동시에 처리할 번역 작업 수를 설정합니다. 값이 높을수록 번역 속도가 빨라지지만, API 할당량을 빠르게 소모할 수 있습니다. 이 숫자는 높을수록 몇개의 파일을 동시에 열고 작업할지를 설정 합니다.",
    )

    file_split_number = st.sidebar.number_input(
        "파일 분할 작업자 수",
        min_value=1,
        max_value=100,
        value=1,
        step=1,
        help="파일 분할 작업자 수를 설정합니다. 값이 높을수록 한개의 파일을 n개로 분할하여 작업하여 속도가 빨라집니다. 하지만 1보다 크게 설정한다면 사전을 동시에 작성하면서 같은 용어를 사용하지 않는 경우가 발생할 수 있습니다. (랜덤 순서 사용 권장장)",
    )

    use_random_order = st.sidebar.checkbox(
        "랜덤 순서로 번역",
        value=False,
        help="랜덤 순서로 번역을 진행하여 병렬 번역시 사전의 정확도를 높입니다.",
    )

    # UI 업데이트 설정
    st.sidebar.subheader("UI 업데이트 설정")
    update_interval = st.sidebar.slider(
        "업데이트 간격(초)",
        min_value=1.0,
        max_value=10.0,
        value=3.0,
        step=0.5,
        help="UI가 업데이트되는 간격을 설정합니다. 값이 낮을수록 실시간으로 정보가 갱신되지만 성능에 영향을 줄 수 있습니다.",
    )

    # 커스텀 사전 업로드
    st.sidebar.header("커스텀 사전")
    custom_dict_file = st.sidebar.file_uploader(
        "커스텀 사전 업로드 (JSON)", type=["json"]
    )

    # 모드팩 선택
    st.header("모드팩 파일 선택")

    # 원본 언어 코드 입력
    source_lang_code = st.text_input(
        "원본 언어 코드",
        "en_us",
        placeholder="번역할 원본 언어 코드를 입력하세요 (예: en_us)",
    ).lower()  # 입력값을 소문자로 변환

    # 폴더 선택 (실제로는 폴더 경로 입력)
    modpack_path = st.text_input(
        "모드팩 폴더 경로",
        "",
        placeholder="폴더 경로를 입력해주세요. (예: C:\\Users\\<<이름>>\\Documents\\Minecraft\\mods\\my_modpack)",
    ).replace("\\", "/")

    # 번역 결과, 기존 번역 자동 사전 구축 옵션
    build_dict_from_existing = st.checkbox("기존 번역에서 사전 자동 구축", value=True)

    # 번역 결과 출력 경로
    output_path = st.text_input(
        "번역 결과 출력 경로",
        "",
        placeholder="경로를 입력해주세요. (예: C:\\Users\\<<이름>>\\Documents\\Minecraft\\mods\\my_modpack\\output)",
    ).replace("\\", "/")

    # 리소스팩 이름 설정
    resourcepack_name = st.text_input("리소스팩 이름", "Auto-Translated-KO")

    output_path = os.path.join(output_path, resourcepack_name)

    # 번역 카테고리 선택
    st.subheader("번역 카테고리 선택")
    translate_config = st.checkbox("Config 파일 번역", value=True)
    translate_kubejs = st.checkbox("KubeJS 파일 번역", value=True)
    translate_mods = st.checkbox("Mods 파일 번역", value=True)

    # 커스텀 사전 처리
    translation_dictionary = {}
    translation_dictionary_lowercase = {}

    # 공식 마인크래프트 번역 파일에서 사전 구축
    try:
        if source_lang_code == "en_us":  # 원본 언어가 영어일 때만 공식 사전 구축
            # 영어-한국어 매핑 생성
            for key, en_value in OFFICIAL_EN_LANG_FILE.items():
                if key in OFFICIAL_KO_LANG_FILE:
                    ko_value = OFFICIAL_KO_LANG_FILE[key]
                    if en_value and ko_value:  # 빈 값이 아닌 경우에만 추가
                        add_to_dictionary(
                            en_value,
                            ko_value,
                            translation_dictionary,
                            translation_dictionary_lowercase,
                        )

            st.sidebar.success(
                f"공식 마인크래프트 번역 사전 로드 완료: {len(translation_dictionary)}개 항목"
            )
        else:
            st.sidebar.warning(
                f"원본 언어 '{source_lang_code}'에 대한 공식 번역 파일이 없어 공식 사전 구축을 건너뛰니다."
            )
            logger.warning(
                f"원본 언어 '{source_lang_code}'에 대한 공식 번역 파일이 없어 공식 사전 구축을 건너뛰니다."
            )

    except Exception as e:
        st.sidebar.warning(f"공식 번역 파일 로드 오류: {str(e)}")
        logger.warning(f"공식 번역 파일 로드 오류: {str(e)}")

    if custom_dict_file is not None:
        try:
            translation_dictionary = json.load(custom_dict_file)
            translation_dictionary_lowercase = {
                k.lower(): k for k, v in translation_dictionary.items()
            }
            st.sidebar.success(
                f"커스텀 사전 로드 완료: {len(translation_dictionary)}개 항목"
            )
        except Exception as e:
            st.sidebar.error(
                f"사전 로드 오류: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
            )
            error_traceback = traceback.format_exc()
            logger.error(error_traceback)

    # 번역 실행 버튼
    if st.button("번역 시작"):
        if not api_keys:
            st.error("API 키를 입력해주세요.")
            return

        if not os.path.exists(modpack_path):
            st.error("모드팩 폴더가 존재하지 않습니다.")
            return

        # 최소한 하나의 카테고리는 선택되어야 함
        if not (translate_config or translate_kubejs or translate_mods):
            st.error("최소한 하나의 번역 카테고리를 선택해주세요.")
            return

        # 번역 시작
        try:
            with st.spinner("번역 진행 중..."):
                # 전체 진행 상황 표시를 위한 상태 표시 바와 정보 표시 영역
                st.subheader("전체 진행 상황")
                progress_cols = st.columns([4, 1])
                with progress_cols[0]:
                    overall_progress_bar = st.progress(0)
                with progress_cols[1]:
                    overall_progress_text = st.empty()
                status_text = st.empty()

                # 로그 영역 설정
                log_container = st.expander("번역 로그", expanded=True)
                logs = []  # 로그 메시지를 저장할 리스트

                # 로그 출력 함수
                def add_log(message, level="info"):
                    logs.append(
                        {
                            "message": message,
                            "level": level,
                            "time": uuid.uuid4().hex[:8],
                        }
                    )
                    with log_container:
                        # 가장 최근 로그 20개만 표시
                        for log in logs[-20:]:
                            if log["level"] == "info":
                                st.info(f"[{log['time']}] {log['message']}")
                            elif log["level"] == "warning":
                                st.warning(f"[{log['time']}] {log['message']}")
                            elif log["level"] == "error":
                                st.error(f"[{log['time']}] {log['message']}")
                            elif log["level"] == "success":
                                st.success(f"[{log['time']}] {log['message']}")

            # 작업자별 진행 상황 컨테이너
            worker_progress_bars = {}
            worker_progress_texts = {}
            worker_status_texts = {}

            # 작업자별 진행 상황 초기화
            for i in range(max_workers):
                st.markdown(f"### Worker {i + 1}")
                worker_cols = st.columns([3, 1])

                with worker_cols[0]:
                    worker_progress_bars[i] = st.progress(0)
                with worker_cols[1]:
                    worker_progress_texts[i] = st.empty()

                worker_status_texts[i] = st.empty()
                st.markdown("---")

            # LLM 인스턴스 생성
            status_text.text("모델 초기화 중...")
            add_log("모델 초기화 중...")

            # 글로벌 API 키 인덱스 초기화
            st.session_state.api_key_index = 0
            total_api_keys = len(api_keys)

            add_log(f"총 {total_api_keys}개의 API 키를 순차적으로 사용합니다.")

            try:
                # Rate Limiter 설정
                rate_limiter = None
                if use_rate_limiter:
                    # RPM을 RPS(초당 요청 수)로 변환
                    rps = rpm / 60.0
                    rate_limiter = InMemoryRateLimiter(
                        requests_per_second=rps,
                        check_every_n_seconds=0.1,
                        max_bucket_size=10,
                    )
                    status_text.text(f"속도 제한: {rpm} RPM ({rps:.2f} RPS)")
                    add_log(f"속도 제한 설정: {rpm} RPM ({rps:.2f} RPS)")
                if use_request_delay:
                    delay_manager = DelayManager(delay=request_delay)
                else:
                    delay_manager = DelayManager(delay=0)
                # 현재 API 키 가져오기
                st.session_state.api_key_index = (
                    st.session_state.api_key_index + 1
                ) % total_api_keys

                add_log(
                    f"API 키 사용 중: {st.session_state.api_key_index}/{total_api_keys}"
                )

            except RuntimeError as e:
                add_log(f"모델 초기화 중 오류 발생: {e}", "error")
                st.error(
                    f"모델 초기화 사용 중 오류가 발생했습니다.\n\n오류 메시지: {e}"
                )
                return

            # 출력 디렉토리 생성
            os.makedirs(output_path, exist_ok=True)
            dictionary_path = os.path.join(output_path, "dictionary")
            os.makedirs(dictionary_path, exist_ok=True)
            add_log(f"출력 디렉토리 생성 완료: {output_path}")

            # UUID 생성 (리소스팩 식별자로 사용)
            uuid_str = str(uuid.uuid4())

            # 모드팩 디렉토리에서 번역할 파일 찾기
            status_text.text("번역 대상 파일 검색 중...")
            add_log("번역 대상 파일 검색 중...")
            source_lang_files, mods_jar_files = process_modpack_directory(
                modpack_path,
                source_lang_code,
                translate_config,
                translate_kubejs,
                translate_mods,
            )

            if len(source_lang_files) == 0:
                add_log("번역할 파일을 찾을 수 없습니다.", "warning")
                st.warning("번역할 파일을 찾을 수 없습니다.")
                return

            status_text.text(f"{len(source_lang_files)}개의 언어 파일을 찾았습니다.")
            add_log(f"{len(source_lang_files)}개의 언어 파일을 찾았습니다.")

            # 기존 번역에서 사전 구축
            if build_dict_from_existing:
                status_text.text("기존 번역에서 사전 구축 중...")
                add_log("기존 번역에서 사전 구축 중...")

                # JAR 파일에서 사전 구축
                (
                    translation_dictionary,
                    translation_dictionary_lowercase,
                    jar_files_count,
                    jar_entries_added,
                ) = build_dictionary_from_jar(
                    mods_jar_files,
                    translation_dictionary,
                    translation_dictionary_lowercase,
                    source_lang_code,
                )
                add_log(
                    f"JAR 파일 {jar_files_count}개에서 {jar_entries_added}개 항목 추가"
                )

                # 일반 파일에서 사전 구축
                (
                    translation_dictionary,
                    translation_dictionary_lowercase,
                    files_count,
                    entries_added,
                ) = build_dictionary_from_files(
                    source_lang_files,
                    modpack_path,
                    translation_dictionary,
                    translation_dictionary_lowercase,
                    source_lang_code,
                )
                add_log(f"일반 파일 {files_count}개에서 {entries_added}개 항목 추가")

                # 사전 정보 표시
                total_files = jar_files_count + files_count
                total_entries = jar_entries_added + entries_added
                add_log(
                    f"총 {total_files}개 파일에서 {total_entries}개 항목을 사전에 추가",
                    "success",
                )

                with log_container:
                    st.info(
                        f"기존 번역에서 {total_files}개 파일을 분석하여 {total_entries}개 항목을 사전에 추가했습니다."
                    )

            # 공유 컨텍스트 생성
            shared_context = TranslationContext(
                translation_graph=create_translation_graph(),
                custom_dictionary_dict=translation_dictionary,
                registry=registry,
            )
            shared_context.initialize_dictionaries()

            try:
                dict_size = len(shared_context.get_dictionary())
                add_log(
                    f"공유 번역 컨텍스트 생성 완료: {dict_size}개 사전 항목",
                    "success",
                )
            except Exception as e:
                add_log(
                    f"공유 컨텍스트 생성은 완료됐으나 사전 정보 확인 중 오류: {e}",
                    "warning",
                )
                add_log("번역은 정상적으로 진행됩니다.", "info")

            status_text.text(
                f"번역을 시작합니다... ({len(translation_dictionary)}개 사전 항목 사용)"
            )
            add_log(
                f"번역 시작 ({len(translation_dictionary)}개 사전 항목 사용)",
                "success",
            )

            # 번역 파일 매핑 (원본 -> 번역)
            translated_files = {}

            # 오류 발생 파일 목록
            failed_files = []

            # 파일 타입별 분류
            file_types = {"config": [], "kubejs": [], "mods": []}

            for file_path in source_lang_files:
                # tmp_ 로 시작하는 파일은 건너뛰기
                if os.path.basename(file_path).startswith("tmp_"):
                    continue

                if "/config/" in file_path or "\\config\\" in file_path:
                    file_types["config"].append(file_path)
                elif "/kubejs/" in file_path or "\\kubejs\\" in file_path:
                    file_types["kubejs"].append(file_path)
                else:
                    file_types["mods"].append(file_path)

            # 선택되지 않은 카테고리 필터링
            if not translate_config:
                file_types["config"] = []
            if not translate_kubejs:
                file_types["kubejs"] = []
            if not translate_mods:
                file_types["mods"] = []

            # 파일 타입별 출력 디렉토리 생성
            with open(
                os.path.join(output_path, "processing_info.json"),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(file_types, f, ensure_ascii=False, indent=4)

            # 카테고리별 번역 진행
            total_files = len(source_lang_files)
            processed_files = 0

            # 작업자별 상태 관리를 위한 딕셔너리
            worker_statuses = {
                i: {"active": False, "file": "", "progress": 0}
                for i in range(max_workers)
            }

            # 번역 시작 시간 기록
            start_time = time.time()
            last_update_time = {}  # 각 워커별 마지막 업데이트 시간
            processing_speeds = []  # 최근 처리 속도 기록 (항목/초)
            max_speed_samples = 10  # 속도 계산에 사용할 최대 샘플 수

            # 진행 상황 업데이트 콜백 함수
            async def update_progress(
                worker_id,
                file_path=None,
                progress=None,
                done=False,
                total_items=None,
                processed_items=None,
            ):
                current_time = time.time()

                # 마지막 업데이트 시간 확인
                if worker_id in last_update_time:
                    # 업데이트 간격이 충분하지 않으면 업데이트 건너뛰기 (파일 완료 시는 제외)
                    if (
                        not done
                        and current_time - last_update_time[worker_id] < update_interval
                    ):
                        return

                # 현재 시간을 마지막 업데이트 시간으로 기록
                last_update_time[worker_id] = current_time

                # 경과 시간 계산
                elapsed_time = current_time - start_time
                hours, remainder = divmod(elapsed_time, 3600)
                minutes, seconds = divmod(remainder, 60)
                elapsed_str = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

                if file_path:
                    worker_statuses[worker_id]["file"] = file_path

                if progress is not None:
                    worker_statuses[worker_id]["progress"] = progress

                if done:
                    worker_statuses[worker_id]["active"] = False
                    nonlocal processed_files
                    processed_files += 1
                    overall_progress = int((processed_files / total_files) * 100)
                    overall_progress_bar.progress(overall_progress)
                    overall_progress_text.markdown(
                        f"**{processed_files}/{total_files}** ({overall_progress}%)"
                    )
                else:
                    worker_statuses[worker_id]["active"] = True

                # 예상 완료 시간 계산 (전체의 1% 이상 처리된 경우에만)
                if (
                    processed_files > 0
                    and processed_files < total_files
                    and elapsed_time > 10
                ):
                    completion_percentage = processed_files / total_files
                    if completion_percentage > 0.01:
                        estimated_total_time = elapsed_time / completion_percentage
                        remaining_time = estimated_total_time - elapsed_time

                        # 남은 시간 형식화
                        r_hours, r_remainder = divmod(remaining_time, 3600)
                        r_minutes, r_seconds = divmod(r_remainder, 60)
                        remaining_str = (
                            f"{int(r_hours):02}:{int(r_minutes):02}:{int(r_seconds):02}"
                        )

                        # 예상 완료 시간 계산
                        import datetime

                        completion_time = datetime.datetime.now() + datetime.timedelta(
                            seconds=remaining_time
                        )

                        # 오늘이면 시간만, 내일 이후면 날짜와 시간 표시
                        today = datetime.datetime.now().date()
                        if completion_time.date() == today:
                            completion_str = completion_time.strftime("%H:%M:%S")
                            completion_display = f"오늘 {completion_str}"
                        elif completion_time.date() == today + datetime.timedelta(
                            days=1
                        ):
                            completion_str = completion_time.strftime("%H:%M:%S")
                            completion_display = f"내일 {completion_str}"
                        else:
                            completion_str = completion_time.strftime("%m/%d %H:%M:%S")
                            completion_display = completion_str

                        time_info = f"경과: {elapsed_str} | 남음: {remaining_str} | 완료 예상: {completion_display}"
                    else:
                        time_info = f"경과: {elapsed_str}"
                else:
                    time_info = f"경과: {elapsed_str}"

                # 작업자 상태 업데이트
                status_prefix = (
                    "🟢 Active"
                    if worker_statuses[worker_id]["active"]
                    else "⚪ Waiting"
                )

                if total_items and processed_items is not None:
                    # 처리 속도 계산 (항목/초)
                    if done and "start_processing_time" in worker_statuses[worker_id]:
                        processing_time = (
                            current_time
                            - worker_statuses[worker_id]["start_processing_time"]
                        )
                        if processing_time > 0:
                            items_per_second = total_items / processing_time
                            processing_speeds.append(items_per_second)
                            # 최근 n개 샘플만 유지
                            if len(processing_speeds) > max_speed_samples:
                                processing_speeds.pop(0)
                    elif (
                        not done
                        and "start_processing_time" not in worker_statuses[worker_id]
                    ):
                        worker_statuses[worker_id]["start_processing_time"] = (
                            current_time
                        )

                    item_progress = f"{processed_items}/{total_items} 항목"
                    worker_status_texts[worker_id].markdown(
                        f"{status_prefix} - **{worker_statuses[worker_id]['file']}** ({item_progress})"
                    )
                else:
                    worker_status_texts[worker_id].markdown(
                        f"{status_prefix} - **{worker_statuses[worker_id]['file']}**"
                    )

                worker_progress_bars[worker_id].progress(
                    worker_statuses[worker_id]["progress"]
                )
                worker_progress_texts[worker_id].markdown(
                    f"**{worker_statuses[worker_id]['progress']}%**"
                )

                # 평균 처리 속도 계산
                avg_speed = (
                    sum(processing_speeds) / len(processing_speeds)
                    if processing_speeds
                    else 0
                )
                speed_info = (
                    f"평균 속도: {avg_speed:.2f} 항목/초"
                    if avg_speed > 0
                    else "평균 속도: 계산중.."
                )

                # 전체 진행 상황 업데이트
                percent_complete = int((processed_files / total_files) * 100)
                status_text.markdown(
                    f"번역 중... **{processed_files}/{total_files}** 파일 완료 ({percent_complete}%) - "
                    f"활성 작업자: {sum(1 for s in worker_statuses.values() if s['active'])}명  \n"
                    f"⏱️ {time_info} | {speed_info} | 업데이트 간격: {update_interval}초"
                )

            # 사전 정렬 및 필터링 함수
            def sort_and_filter_dictionary():
                sorted_dict = {}
                for k, v in sorted(
                    translation_dictionary.items(),
                    key=lambda item: len(item[0]),
                    reverse=True,
                ):
                    if (
                        len(k.split(" ")) <= 10
                        and not re.search(r"[.?!%]", k)
                        and not re.search(
                            r"[.?!%]", ", ".join(v) if isinstance(v, list) else v
                        )
                    ):
                        if isinstance(v, list):
                            sorted_dict[k] = v
                        else:
                            sorted_dict[k] = v
                return sorted_dict

            # 각 카테고리별 처리 디렉토리 생성
            for category in ["config", "kubejs", "mods"]:
                os.makedirs(os.path.join(output_path, category, "input"), exist_ok=True)
                os.makedirs(
                    os.path.join(output_path, category, "output"), exist_ok=True
                )

            # 단일 파일 번역 함수
            async def translate_file(worker_id, en_file, category):
                try:
                    # 작업자 상태 업데이트
                    await update_progress(worker_id, en_file, 0)

                    # 현재 API 키 가져오기
                    current_api_key = api_keys[
                        st.session_state.api_key_index % total_api_keys
                    ]

                    # 다음 API 키 인덱스로 업데이트
                    st.session_state.api_key_index = (
                        st.session_state.api_key_index + 1
                    ) % total_api_keys

                    # 파일 이름이 tmp_로 시작하면 건너뛰기
                    if os.path.basename(en_file).startswith("tmp_"):
                        await update_progress(worker_id, en_file, 100, True)
                        return

                    # 출력 파일 경로 설정
                    rel_path = en_file.replace(modpack_path, "").lstrip("/\\")

                    # 카테고리별 출력 경로 설정
                    input_file = os.path.join(
                        output_path,
                        category,
                        "input",
                        rel_path.replace(source_lang_code, LANG_CODE, 1),
                    )

                    output_file = os.path.join(
                        output_path,
                        category,
                        "output",
                        rel_path.replace(source_lang_code, LANG_CODE, 1),
                    )

                    try:
                        # 입력 파일 내용 추출
                        en_data = extract_lang_content(en_file)
                        if not en_data:
                            await update_progress(worker_id, en_file, 100, True)
                            return

                        # 데이터가 사전이 아니면 건너뛰기
                        if not isinstance(en_data, dict):
                            await update_progress(worker_id, en_file, 100, True)
                            return

                        # 입력 디렉토리 생성 및 파일 저장
                        input_dir = os.path.dirname(input_file)
                        os.makedirs(input_dir, exist_ok=True)

                        with open(input_file, "w", encoding="utf-8") as f:
                            json.dump(en_data, f, ensure_ascii=False, indent=4)

                        # 번역 처리
                        nonlocal translation_dictionary
                        nonlocal translation_dictionary_lowercase
                        translation_dictionary = sort_and_filter_dictionary()

                        # 임시 파일 경로 설정
                        temp_output_path = output_file + ".tmp"

                        # 임시 출력 디렉토리 반드시 생성
                        output_dir = os.path.dirname(output_file)
                        os.makedirs(output_dir, exist_ok=True)

                        # 번역 파일의 총 항목 수
                        total_items = len(en_data)
                        processed_items = 0

                        # 번역 함수 정의
                        async def progress_callback():
                            # 현재 진행 중인 항목 수 기반으로 진행 상황 업데이트
                            nonlocal en_data
                            nonlocal processed_items
                            items_count = len(en_data)
                            if items_count > 0:
                                # 처리된 항목 수 증가
                                processed_items = min(
                                    processed_items + 1,
                                    items_count - 1,
                                )

                                # 진행률 계산
                                progress_percent = int(
                                    (processed_items / items_count) * 100
                                )

                                # 작업자의 진행 상황 업데이트 (최대 95%까지)
                                new_progress = min(progress_percent, 95)
                                await update_progress(
                                    worker_id,
                                    None,
                                    new_progress,
                                    False,
                                    total_items,
                                    processed_items,
                                )

                        # 번역 실행
                        try:
                            await minecraft_modpack_auto_translator.translate_json_file(
                                input_path=input_file,
                                output_path=temp_output_path,  # 임시 파일에 JSON으로 저장
                                custom_dictionary_dict=translation_dictionary,
                                llm=get_translator(
                                    provider=model_provider.lower(),
                                    api_key=current_api_key,
                                    model_name=selected_model,
                                    api_base=api_base_url,
                                    temperature=temperature,
                                    rate_limiter=rate_limiter,
                                ),
                                max_workers=file_split_number,  # 단일 파일 내에서는 병렬 처리 안함
                                progress_callback=progress_callback,
                                external_context=shared_context,  # 공유 컨텍스트 사용
                                delay_manager=delay_manager,
                                use_random_order=use_random_order,
                            )

                            # 모든 항목 처리 완료
                            processed_items = total_items
                            await update_progress(
                                worker_id,
                                None,
                                95,
                                False,
                                total_items,
                                processed_items,
                            )

                            # 사전 저장 (임시 파일에)
                            # 동시성 문제 방지를 위해 사전의 복사본 생성
                            try:
                                dictionary_copy = dict(shared_context.get_dictionary())
                                with open(
                                    os.path.join(output_path, "shared_dict.json"),
                                    "w",
                                    encoding="utf-8",
                                ) as f:
                                    json.dump(
                                        dictionary_copy,
                                        f,
                                        ensure_ascii=False,
                                        indent=4,
                                    )
                            except Exception as e:
                                logger.debug(f"사전 저장 중 오류 발생: {e}")

                            # 원래 파일 형식으로 변환
                            if os.path.exists(temp_output_path):
                                file_ext = os.path.splitext(en_file)[1]
                                parser_class = get_parser_by_extension(file_ext)

                                if parser_class:
                                    # 임시 JSON 파일에서 데이터 로드
                                    with open(
                                        temp_output_path, "r", encoding="utf-8"
                                    ) as f:
                                        data = json.load(f)

                                    # 원본 파일 형식으로 변환
                                    content = parser_class.save(data)

                                    # 최종 파일 저장
                                    with open(output_file, "w", encoding="utf-8") as f:
                                        f.write(content)

                                    # # 임시 파일 삭제
                                    # try:
                                    #     os.remove(temp_output_path)
                                    # except OSError:
                                    #     logger.warning(
                                    #         f"임시 파일을 삭제할 수 없습니다: {temp_output_path}"
                                    #     )

                                    # 작업 완료 표시
                                    await update_progress(
                                        worker_id,
                                        None,
                                        100,
                                        True,
                                        total_items,
                                        total_items,
                                    )
                                else:
                                    logger.warning(
                                        f"지원되지 않는 파일 형식: {file_ext}"
                                    )
                                    await update_progress(worker_id, None, 100, True)
                            else:
                                logger.warning(
                                    f"번역 결과 파일이 생성되지 않았습니다: {temp_output_path}"
                                )
                                await update_progress(worker_id, None, 100, True)

                        except Exception as e:
                            logger.error(
                                f"파일 처리 중 오류 발생: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
                            )
                            logger.error(traceback.format_exc())

                            # 오류 파일 기록
                            failed_file_info = {
                                "path": en_file,
                                "error": str(e),
                                "category": category,
                            }
                            failed_files.append(failed_file_info)

                            await update_progress(worker_id, en_file, 100, True)

                    except Exception as e:
                        logger.error(
                            f"파일 처리 중 오류 발생: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
                        )
                        logger.error(traceback.format_exc())

                        # 오류 파일 기록
                        failed_file_info = {
                            "path": en_file,
                            "error": str(e),
                            "category": category,
                        }
                        failed_files.append(failed_file_info)

                        await update_progress(worker_id, en_file, 100, True)

                except Exception as e:
                    error_traceback = traceback.format_exc()
                    logger.error(
                        f"파일 번역 중 오류: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
                    )
                    logger.error(error_traceback)

                    # 오류 파일 기록
                    failed_file_info = {
                        "path": en_file,
                        "error": str(e),
                        "category": category,
                    }
                    failed_files.append(failed_file_info)

                    await update_progress(worker_id, en_file, 100, True)

            # 병렬 번역 실행 함수
            async def run_translation():
                # 모든 카테고리의 파일을 하나의 리스트로 통합
                all_files = []
                for category, files in file_types.items():
                    for f in files:
                        all_files.append((f, category))

                # 작업 큐 생성
                queue = asyncio.Queue()

                # 큐에 모든 파일 추가
                for file_tuple in all_files:
                    await queue.put(file_tuple)

                # 워커 함수 정의
                async def worker(worker_id):
                    while not queue.empty():
                        try:
                            file_path, category = await queue.get()
                            await translate_file(worker_id, file_path, category)
                            queue.task_done()
                        except Exception as e:
                            logger.error(f"워커 {worker_id} 오류: {e}")
                            queue.task_done()

                # 워커 시작
                workers = []
                for i in range(max_workers):
                    task = asyncio.create_task(worker(i))
                    workers.append(task)

                # 모든 작업 완료 대기
                await queue.join()

                # 워커 태스크 취소
                for task in workers:
                    task.cancel()

                # 취소된 태스크 처리 완료 대기
                await asyncio.gather(*workers, return_exceptions=True)

            # 비동기 번역 실행
            asyncio.run(run_translation())

            # 리소스팩 생성
            overall_progress_bar.progress(95)
            overall_progress_text.markdown(f"**{total_files}/{total_files}** (95%)")
            status_text.markdown("리소스팩 생성 중...")

            # 카테고리별 리소스팩 정보
            categories = {
                "mods": {
                    "name": "Mods",
                    "suffix": "_MOD_TRANSLATION",
                    "emoji": "🟢",
                    "icon": "🎮",
                    "warning": False,
                },
                "config": {
                    "name": "Config",
                    "suffix": "_CONFIG_TRANSLATION",
                    "emoji": "🔷",
                    "icon": "⚙️",
                    "warning": "Config 파일은 모드팩에 따라 리소스팩으로 인식되지 못하는 경우가 있을 수 있습니다. 압축을 모드팩 Client 폴더에 풀어서 덮어쓰기 하세요.",
                },
                "kubejs": {
                    "name": "KubeJS",
                    "suffix": "_KUBEJS_TRANSLATION",
                    "emoji": "🟡",
                    "icon": "📜",
                    "warning": "KubeJS 파일은 모드팩에 따라 리소스팩으로 인식되지 못하는 경우가 있을 수 있습니다. 압축을 모드팩 Client 폴더에 풀어서 덮어쓰기 하세요.",
                },
            }

            # 생성된 리소스팩을 저장할 리스트와 카테고리별 분류
            created_resourcepacks = []
            category_packs = {"All": []}

            # 카테고리별 리소스팩 생성
            for category, info in categories.items():
                # 선택되지 않은 카테고리는 건너뜀
                if (
                    (category == "config" and not translate_config)
                    or (category == "kubejs" and not translate_kubejs)
                    or (category == "mods" and not translate_mods)
                ):
                    continue

                output_dir = os.path.join(output_path, category, "output", "**")
                output_glob_path = normalize_glob_path(output_dir)
                if len(glob(output_glob_path, recursive=True)) > 1:
                    # 리소스팩 생성
                    resourcepack_zip = create_resourcepack(
                        output_path,
                        [f"{output_path}/{category}/output"],
                        resourcepack_name + info["suffix"],
                    )

                    # 생성된 리소스팩 정보 저장
                    pack_info = {
                        "category": category,
                        "info": info,
                        "path": resourcepack_zip,
                    }
                    created_resourcepacks.append(pack_info)

                    # 카테고리별 분류에도 추가
                    category_name = info["name"]
                    if category_name not in category_packs:
                        category_packs[category_name] = []
                    category_packs[category_name].append(pack_info)
                    category_packs["All"].append(pack_info)

            # 리소스팩이 생성되었을 경우에만 표시
            if created_resourcepacks:
                st.header("🎯 번역 결과")

                # 탭 생성 - 모두 + 각 카테고리별
                tab_titles = ["All"]
                for pack in created_resourcepacks:
                    cat_name = pack["info"]["name"]
                    if cat_name not in tab_titles:
                        tab_titles.append(cat_name)

                tabs = st.tabs(tab_titles)

                # 각 탭 내용 채우기
                for i, tab_name in enumerate(tab_titles):
                    with tabs[i]:
                        for pack in category_packs[tab_name]:
                            info = pack["info"]
                            cat_name = info["name"]

                            # 확장 가능한 섹션으로 표시
                            with st.expander(
                                f"{info['icon']} {cat_name} 리소스팩", expanded=True
                            ):
                                # 파일 경로와 다운로드 영역
                                st.code(
                                    f"📁 {pack['path']}",
                                    language=None,
                                )

                                # 사용 방법 안내
                                st.info(
                                    "💡 **사용 방법**\n\n마인크래프트 설정에서 리소스팩 탭을 선택하여 이 리소스팩을 적용하세요."
                                )

                                # 경고 메시지가 있는 경우 표시
                                if info["warning"]:
                                    st.warning(f"⚠️ **주의사항**\n\n{info['warning']}")
            else:
                st.warning("번역된 파일이 없어 리소스팩이 생성되지 않았습니다.")

            # 최종 진행 상황
            overall_progress_bar.progress(100)
            overall_progress_text.markdown(f"**{total_files}/{total_files}** (100%)")
            status_text.markdown("번역 완료!")

            # 최종 사전 저장
            final_dict_path = os.path.join(
                output_path, "total_dictionary", f"{uuid_str}_final.json"
            )
            os.makedirs(os.path.dirname(final_dict_path), exist_ok=True)
            # 공유 컨텍스트의 사전 저장
            shared_dict = shared_context.get_dictionary()
            with open(final_dict_path, "w", encoding="utf-8") as f:
                json.dump(shared_dict, f, ensure_ascii=False, indent=4)

            add_log(f"최종 공유 사전 크기: {len(shared_dict)}개 항목", "success")

            # 결과 표시
            st.success(
                f"번역이 완료되었습니다! 총 {len(translated_files)}개의 파일은 건너뛰고 번역 되었습니다. 번역 사전은 {len(shared_dict)}개 항목으로 구성되었습니다."
            )

            # 오류 발생 파일 표시
            if failed_files:
                with st.expander(
                    f"오류 발생 파일 목록 ({len(failed_files)}개)", expanded=False
                ):
                    for i, failed_file in enumerate(failed_files):
                        file_basename = os.path.basename(failed_file["path"])
                        st.markdown(
                            f"**{i + 1}. {file_basename}** ({failed_file['category']})"
                        )
                        st.markdown(f"  - 경로: `{failed_file['path']}`")
                        st.markdown(f"  - 오류: {failed_file['error']}")
                        st.markdown("---")

                # 오류 파일 목록 저장
                failed_list_path = os.path.join(output_path, "failed_files.json")
                with open(failed_list_path, "w", encoding="utf-8") as f:
                    json.dump(failed_files, f, ensure_ascii=False, indent=4)

                st.warning(
                    f"오류 발생 파일 목록이 {failed_list_path}에 저장되었습니다. 해당 파일들은 '__FAILED__' 접두어가 붙은 파일로 복사되어 있습니다."
                )

        except Exception as e:
            error_traceback = traceback.format_exc()
            st.error(
                f"파일 번역 중 오류: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
            )
            logger.error(error_traceback)


if __name__ == "__main__":
    main()
