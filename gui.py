import json
import logging
import os
import re
import shutil
import traceback
import uuid
import zipfile
from glob import glob

import streamlit as st
from langchain_core.rate_limiters import InMemoryRateLimiter

import minecraft_modpack_auto_translator
from minecraft_modpack_auto_translator import create_resourcepack
from minecraft_modpack_auto_translator.config import (
    DICTIONARY_PREFIX_WHITELIST,
    DICTIONARY_SUFFIX_BLACKLIST,
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
    """번역 사전에 항목을 추가합니다."""
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


def build_dictionary_from_files(
    en_us_files, modpack_path, translation_dictionary, translation_dictionary_lowercase
):
    """영어 파일과 해당하는 한국어 파일에서 번역 사전을 구축합니다."""

    file_count = 0
    entries_added = 0

    for en_file in en_us_files:
        try:
            # 한국어 파일 경로 추정
            rel_path = en_file.replace(modpack_path, "").lstrip("/\\")
            ko_file = os.path.join(
                modpack_path,
                rel_path.replace("en_us", LANG_CODE).replace("en_US", LANG_CODE),
            )

            # 한국어 파일이 존재하는 경우
            if os.path.exists(ko_file):
                # 파일 내용 로드
                en_data = extract_lang_content(en_file)
                ko_data = extract_lang_content(ko_file)

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
    jar_files, translation_dictionary, translation_dictionary_lowercase
):
    """JAR 파일 내부의 언어 파일에서 번역 사전을 구축합니다."""

    file_count = 0
    entries_added = 0
    supported_extensions = get_supported_extensions()

    for jar_path in jar_files:
        try:
            with zipfile.ZipFile(jar_path, "r") as jar:
                # 영어 파일 찾기
                en_lang_files = [
                    f
                    for f in jar.namelist()
                    if os.path.splitext(f)[1] in supported_extensions
                    and ("en_us" in f.lower() or "en_US" in f.lower())
                ]

                for en_file in en_lang_files:
                    # 한국어 파일 경로 추정
                    ko_file = en_file.replace("en_us", LANG_CODE).replace(
                        "en_US", LANG_CODE
                    )

                    # 두 파일이 모두 존재하는 경우
                    if ko_file in jar.namelist():
                        try:
                            # 파일 내용 로드
                            with jar.open(en_file, "r") as f:
                                file_bytes = f.read()
                                en_content = file_bytes.decode("utf-8", errors="ignore")

                            with jar.open(ko_file, "r") as f:
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


def process_modpack_directory(modpack_path):
    """모드팩 디렉토리에서 번역 대상 파일을 찾습니다."""
    supported_extensions = get_supported_extensions()

    # 번역 대상 파일 검색
    en_us_files = []

    # config 폴더 내 파일 검색
    config_files = glob(os.path.join(modpack_path, "config/**/*.*"), recursive=True)
    for f in config_files:
        file_ext = os.path.splitext(f)[1]
        if file_ext in supported_extensions and ("en_us" in f or "en_US" in f):
            en_us_files.append(f)

    # kubejs 폴더 내 파일 검색
    kubejs_files = glob(os.path.join(modpack_path, "kubejs/**/*.*"), recursive=True)
    for f in kubejs_files:
        file_ext = os.path.splitext(f)[1]
        if file_ext in supported_extensions and ("en_us" in f or "en_US" in f):
            en_us_files.append(f)

    # mods 폴더 내 jar 파일 검색
    mods_jar_files = glob(os.path.join(modpack_path, "mods/*.jar"))

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
                    and ("en_us" in f.lower() or "en_US" in f.lower())
                ]

                for lang_file in lang_files:
                    # 임시 디렉토리에 파일 추출
                    extract_path = os.path.join(
                        extract_dir, os.path.basename(jar_path), lang_file
                    )
                    os.makedirs(os.path.dirname(extract_path), exist_ok=True)

                    with (
                        jar.open(lang_file) as source,
                        open(extract_path, "wb") as target,
                    ):
                        shutil.copyfileobj(source, target)

                    en_us_files.append(extract_path)
        except Exception as e:
            st.error(
                f"JAR 파일 처리 중 오류: {e}, {jar_path}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
            )
            error_traceback = traceback.format_exc()
            logger.error(error_traceback)

    return en_us_files, mods_jar_files


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
            f"파일 내용 추출 중 오류: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
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

    # 사이드바에 모델 선택 옵션
    st.sidebar.header("번역 설정")

    # LLM 모델 선택
    model_provider = st.sidebar.selectbox(
        "AI 모델 제공자 선택", ["OpenAI", "Google", "Grok", "Ollama", "Anthropic"]
    )

    # 모델 제공자에 따른 키와 모델 입력 필드
    env_api_key = os.getenv(API_KEY_ENV_VARS.get(model_provider, ""))
    api_key = st.sidebar.text_input(
        f"{model_provider} API 키",
        value=env_api_key if env_api_key else "",
        type="password",
    )

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
        max_value=1.0,
        value=0.1,
        step=0.05,
        help="값이 낮을수록 더 창의성이 낮은 응답이, 높을수록 더 창의성이 높은 응답이 생성됩니다.",
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

    # 커스텀 사전 업로드
    st.sidebar.header("커스텀 사전")
    custom_dict_file = st.sidebar.file_uploader(
        "커스텀 사전 업로드 (JSON)", type=["json"]
    )

    # 모드팩 선택
    st.header("모드팩 파일 선택")

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

    # 옵션: 이미 번역된 파일은 건너뛰기
    skip_translated = st.checkbox("이미 번역된 파일은 건너뛰기", value=True)

    # 리소스팩 이름 설정
    resourcepack_name = st.text_input("리소스팩 이름", "Auto-Translated-KO")

    output_path = os.path.join(output_path, resourcepack_name)

    # 커스텀 사전 처리
    translation_dictionary = {}
    translation_dictionary_lowercase = {}

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
        if not api_key:
            st.error("API 키를 입력해주세요.")
            return

        if not os.path.exists(modpack_path):
            st.error("모드팩 폴더가 존재하지 않습니다.")
            return

        # 번역 시작
        try:
            with st.spinner("번역 진행 중..."):
                # 진행 상황 표시를 위한 상태 표시 바
                progress_bar = st.progress(0)
                status_text = st.empty()

                # LLM 인스턴스 생성
                status_text.text("모델 초기화 중...")

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

                    llm = get_translator(
                        provider=model_provider.lower(),
                        api_key=api_key,
                        model_name=selected_model,
                        api_base=api_base_url,
                        temperature=temperature,
                        rate_limiter=rate_limiter,
                    )
                except RuntimeError as e:
                    st.error(
                        f"모델 초기화 사용 중 오류가 발생했습니다.\n\n오류 메시지: {e}"
                    )
                    return

                # 출력 디렉토리 생성
                os.makedirs(output_path, exist_ok=True)
                dictionary_path = os.path.join(output_path, "dictionary")
                os.makedirs(dictionary_path, exist_ok=True)

                # UUID 생성 (리소스팩 식별자로 사용)
                uuid_str = str(uuid.uuid4())

                # 모드팩 디렉토리에서 번역할 파일 찾기
                status_text.text("번역 대상 파일 검색 중...")
                en_us_files, mods_jar_files = process_modpack_directory(modpack_path)

                if len(en_us_files) == 0:
                    st.warning("번역할 파일을 찾을 수 없습니다.")
                    return

                status_text.text(f"{len(en_us_files)}개의 언어 파일을 찾았습니다.")

                # 기존 번역에서 사전 구축
                if build_dict_from_existing:
                    status_text.text("기존 번역에서 사전 구축 중...")

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
                    )

                    # 일반 파일에서 사전 구축
                    (
                        translation_dictionary,
                        translation_dictionary_lowercase,
                        files_count,
                        entries_added,
                    ) = build_dictionary_from_files(
                        en_us_files,
                        modpack_path,
                        translation_dictionary,
                        translation_dictionary_lowercase,
                    )

                    # 사전 정보 표시
                    total_files = jar_files_count + files_count
                    total_entries = jar_entries_added + entries_added
                    st.info(
                        f"기존 번역에서 {total_files}개 파일을 분석하여 {total_entries}개 항목을 사전에 추가했습니다."
                    )

                status_text.text(
                    f"번역을 시작합니다... ({len(translation_dictionary)}개 사전 항목 사용)"
                )

                # 번역 파일 매핑 (원본 -> 번역)
                translated_files = {}

                # 파일 타입별 분류
                file_types = {"config": [], "kubejs": [], "mods": []}

                for file_path in en_us_files:
                    if "/config/" in file_path or "\\config\\" in file_path:
                        file_types["config"].append(file_path)
                    elif "/kubejs/" in file_path or "\\kubejs\\" in file_path:
                        file_types["kubejs"].append(file_path)
                    else:
                        file_types["mods"].append(file_path)

                # 카테고리별 번역 진행
                total_files = len(en_us_files)
                processed_files = 0
                dictionary_idx = 0

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
                    os.makedirs(
                        os.path.join(output_path, category, "input"), exist_ok=True
                    )
                    os.makedirs(
                        os.path.join(output_path, category, "output"), exist_ok=True
                    )

                # 각 카테고리 번역
                for category, files in file_types.items():
                    for i, en_file in enumerate(files):
                        try:
                            # 진행 상황 업데이트
                            processed_files += 1
                            progress = (processed_files / total_files) * 100
                            progress_bar.progress(int(progress))
                            status_text.text(
                                f"번역 중... ({processed_files}/{total_files}) - {en_file}"
                            )

                            # 출력 파일 경로 설정
                            rel_path = en_file.replace(modpack_path, "").lstrip("/\\")

                            # 카테고리별 출력 경로 설정
                            input_file = os.path.join(
                                output_path,
                                category,
                                "input",
                                rel_path.replace("en_us", LANG_CODE).replace(
                                    "en_US", LANG_CODE
                                ),
                            )

                            output_file = os.path.join(
                                output_path,
                                category,
                                "output",
                                rel_path.replace("en_us", LANG_CODE).replace(
                                    "en_US", LANG_CODE
                                ),
                            )

                            # 이미 번역된 파일은 건너뛰기
                            if skip_translated and os.path.exists(output_file):
                                status_text.text(
                                    f"이미 번역된 파일: {os.path.basename(en_file)}"
                                )
                                translated_files[en_file] = output_file
                                continue

                            try:
                                # 입력 파일 내용 추출
                                en_data = extract_lang_content(en_file)
                                if not en_data:
                                    continue

                                # 데이터가 사전이 아니면 건너뛰기
                                if not isinstance(en_data, dict):
                                    status_text.text(
                                        f"처리할 수 없는 형식: {os.path.basename(en_file)}"
                                    )
                                    continue

                                # 입력 디렉토리 생성 및 파일 저장
                                input_dir = os.path.dirname(input_file)
                                os.makedirs(input_dir, exist_ok=True)

                                with open(input_file, "w", encoding="utf-8") as f:
                                    json.dump(en_data, f, ensure_ascii=False, indent=4)

                                # 번역 처리
                                translation_dictionary = sort_and_filter_dictionary()

                                # 임시 파일 경로 설정
                                temp_output_path = output_file + ".tmp"

                                # 임시 출력 디렉토리 반드시 생성
                                output_dir = os.path.dirname(output_file)
                                os.makedirs(output_dir, exist_ok=True)

                                # 번역 실행
                                try:
                                    translation_dictionary = minecraft_modpack_auto_translator.translate_json_file(
                                        input_path=input_file,
                                        output_path=temp_output_path,  # 임시 파일에 JSON으로 저장
                                        custom_dictionary_dict=translation_dictionary,
                                        llm=llm,
                                    )
                                except RuntimeError as api_error:
                                    # API 할당량 초과 또는 심각한 LLM 오류 처리
                                    error_msg = str(api_error).lower()

                                    if any(
                                        term in error_msg
                                        for term in [
                                            "rate limit",
                                            "quota",
                                            "exceeded",
                                            "too many requests",
                                            "429",
                                        ]
                                    ):
                                        st.error(
                                            f"API 할당량 초과로 번역이 중단되었습니다. 잠시 후 다시 시도해주세요.\n\n오류 메시지: {api_error}"
                                        )
                                    elif any(
                                        term in error_msg
                                        for term in [
                                            "auth",
                                            "key",
                                            "permission",
                                            "unauthorized",
                                            "401",
                                            "403",
                                        ]
                                    ):
                                        st.error(
                                            f"API 인증 오류가 발생했습니다. API 키를 확인해주세요.\n\n오류 메시지: {api_error}"
                                        )
                                    elif any(
                                        term in error_msg
                                        for term in [
                                            "server",
                                            "500",
                                            "502",
                                            "503",
                                            "504",
                                        ]
                                    ):
                                        st.error(
                                            f"API 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.\n\n오류 메시지: {api_error}"
                                        )
                                    elif any(
                                        term in error_msg
                                        for term in [
                                            "context",
                                            "token",
                                            "length",
                                            "too long",
                                        ]
                                    ):
                                        st.error(
                                            f"텍스트가 너무 길어 번역할 수 없습니다. 더 작은 파일로 분할하거나 다른 모델을 사용해보세요.\n\n오류 메시지: {api_error}"
                                        )
                                    else:
                                        st.error(
                                            f"API 호출 중 오류가 발생했습니다.\n\n오류 메시지: {api_error}"
                                        )

                                    # 중간 결과 및 사전 저장
                                    st.warning(
                                        "오류 발생 시점까지의 번역 결과를 저장합니다..."
                                    )

                                    # 사전 저장
                                    dict_path = os.path.join(
                                        output_path,
                                        "total_dictionary",
                                        f"{uuid_str}_error_dictionary.json",
                                    )
                                    os.makedirs(
                                        os.path.dirname(dict_path), exist_ok=True
                                    )
                                    with open(dict_path, "w", encoding="utf-8") as f:
                                        json.dump(
                                            translation_dictionary,
                                            f,
                                            ensure_ascii=False,
                                            indent=4,
                                        )

                                    st.info(
                                        f"현재까지의 번역 사전이 {dict_path}에 저장되었습니다."
                                    )
                                    return

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
                                        with open(
                                            output_file, "w", encoding="utf-8"
                                        ) as f:
                                            f.write(content)

                                        # 임시 파일 삭제
                                        try:
                                            os.remove(temp_output_path)
                                        except OSError:
                                            st.warning(
                                                f"임시 파일을 삭제할 수 없습니다: {temp_output_path}"
                                            )
                                    else:
                                        st.warning(
                                            f"지원되지 않는 파일 형식: {file_ext}"
                                        )
                                else:
                                    st.warning(
                                        f"번역 결과 파일이 생성되지 않았습니다: {temp_output_path}"
                                    )
                            except Exception as e:
                                st.error(
                                    f"파일 처리 중 오류 발생: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
                                )
                                error_traceback = traceback.format_exc()
                                logger.error(error_traceback)
                                continue

                            # 번역 사전 저장
                            os.makedirs(
                                os.path.join(output_path, "total_dictionary", uuid_str),
                                exist_ok=True,
                            )
                            with open(
                                f"{output_path}/total_dictionary/{uuid_str}/{dictionary_idx:03d}.json",
                                "w",
                                encoding="utf-8",
                            ) as f:
                                json.dump(
                                    translation_dictionary,
                                    f,
                                    ensure_ascii=False,
                                    indent=4,
                                )
                            dictionary_idx += 1

                            # 번역 완료 파일 매핑 추가
                            translated_files[en_file] = output_file

                            # 번역 결과를 사전에 추가
                            if os.path.exists(output_file):
                                output_data = extract_lang_content(output_file)
                                if isinstance(output_data, dict):
                                    for key, en_value in en_data.items():
                                        if (
                                            key in output_data
                                            and isinstance(en_value, str)
                                            and isinstance(output_data[key], str)
                                        ):
                                            ko_value = output_data[key]

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

                        except Exception as e:
                            error_traceback = traceback.format_exc()
                            st.error(
                                f"파일 번역 중 오류: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
                            )
                            logger.error(error_traceback)

                # 리소스팩 생성
                progress_bar.progress(95)
                status_text.text("리소스팩 생성 중...")

                resourcepack_zips = []

                if os.path.exists(output_path + "/mods/output"):
                    resourcepack_zip = create_resourcepack(
                        output_path,
                        [
                            output_path + "/mods/output",
                        ],
                        resourcepack_name + "_MOD_TRANSLATION",
                    )
                    resourcepack_zips.append(resourcepack_zip)

                if os.path.exists(output_path + "/config/output"):
                    resourcepack_zip = create_resourcepack(
                        output_path,
                        [
                            output_path + "/config/output",
                        ],
                        resourcepack_name + "_CONFIG_TRANSLATION",
                    )
                    resourcepack_zips.append(resourcepack_zip)

                if os.path.exists(output_path + "/kubejs/output"):
                    resourcepack_zip = create_resourcepack(
                        output_path,
                        [
                            output_path + "/kubejs/output",
                        ],
                        resourcepack_name + "_KUBEJS_TRANSLATION",
                    )
                    resourcepack_zips.append(resourcepack_zip)

                # 최종 진행 상황
                progress_bar.progress(100)
                status_text.text("번역 완료!")

                # 최종 사전 저장
                final_dict_path = os.path.join(
                    output_path, "total_dictionary", f"{uuid_str}_final.json"
                )
                with open(final_dict_path, "w", encoding="utf-8") as f:
                    json.dump(translation_dictionary, f, ensure_ascii=False, indent=4)

                # 결과 표시
                st.success(
                    f"번역이 완료되었습니다! 총 {len(translated_files)}개의 파일이 번역되었습니다. 번역 사전은 {len(translation_dictionary)}개 항목으로 구성되었습니다."
                )
                if resourcepack_zips:
                    st.info(
                        f"리소스팩이 생성되었습니다! ({', '.join(resourcepack_zips)})"
                    )

        except Exception as e:
            error_traceback = traceback.format_exc()
            st.error(
                f"파일 번역 중 오류: {str(e)}\n\n상세 오류 정보는 콘솔 창에서 확인해주세요."
            )
            logger.error(error_traceback)


if __name__ == "__main__":
    main()
