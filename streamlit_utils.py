import json
import logging
import os
import sys
import time
import traceback

import streamlit as st
from langchain_core.rate_limiters import InMemoryRateLimiter

# Windows 환경에서 asyncio 이벤트 루프 정책 설정
if sys.platform.startswith("win"):
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from minecraft_modpack_auto_translator.config import (
    OFFICIAL_EN_LANG_FILE,
    OFFICIAL_KO_LANG_FILE,
)
from minecraft_modpack_auto_translator.delay_manager import DelayManager
from minecraft_modpack_auto_translator.parsers.base_parser import (
    BaseParser,  # Import BaseParser
)

logger = logging.getLogger(__name__)

# --- API 서버 관련 ---

_api_server_thread = None


# --- 로깅 관련 ---


class StreamlitLogHandler(logging.Handler):
    def __init__(self, container, max_log_lines=100):
        super().__init__()
        self.container = container
        self.max_log_lines = max_log_lines
        self.log_messages = []
        self.log_area = self.container.empty()

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_messages.append(msg)
            if len(self.log_messages) > self.max_log_lines:
                self.log_messages = self.log_messages[-self.max_log_lines :]
            self.log_area.markdown("  \n".join(self.log_messages))
        except Exception:
            self.log_messages.append(f"Log formatting error: {record.msg}")
            if len(self.log_messages) > self.max_log_lines:
                self.log_messages = self.log_messages[-self.max_log_lines :]
            self.log_area.markdown("  \n".join(self.log_messages))

    def clear_logs(self):
        self.log_messages = []
        self.log_area.empty()


def setup_logging(max_log_lines=100):
    """Streamlit UI에 로그를 표시하도록 로깅 설정"""
    with st.expander("로그 보기"):
        log_container = st.container()
        handler = StreamlitLogHandler(log_container, max_log_lines)
        handler.setLevel(logging.INFO)

        # 루트 로거 및 모듈 로거에 핸들러 추가
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)  # Ensure root logger level is appropriate

        # Ensure minecraft_modpack_auto_translator logger also gets the handler
        modpack_logger = logging.getLogger("minecraft_modpack_auto_translator")
        # Avoid adding handler if it already exists to prevent duplicate logs
        if handler not in modpack_logger.handlers:
            modpack_logger.addHandler(handler)
        modpack_logger.setLevel(
            logging.INFO
        )  # Ensure modpack logger level is appropriate

        return handler


# --- API 설정 관련 ---

API_KEY_ENV_VARS = {
    "OpenAI": "OPENAI_API_KEY",
    "Google": "GOOGLE_API_KEY",
    "Grok": "GROK_API_KEY",
    "Ollama": "OLLAMA_API_KEY",
    "Anthropic": "ANTHROPIC_API_KEY",
}

API_BASE_ENV_VARS = {
    "OpenAI": "OPENAI_API_BASE",
    "Google": "GOOGLE_API_BASE",
    "Grok": "GROK_API_BASE",
    "Ollama": "OLLAMA_API_BASE",
    "Anthropic": "ANTHROPIC_API_BASE",
}

MODEL_OPTIONS = {
    "OpenAI": ["gpt-4.5-preview", "gpt-4o", "gpt-4o-mini"],
    "Google": ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
    "Grok": ["grok-2-1212"],
    "Ollama": ["직접 입력 하세요."],
    "Anthropic": ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022"],
    "G4F": ["gpt-4o"],
}


def render_model_provider_selection():
    """AI 모델 제공자 선택 UI 렌더링"""
    model_provider = st.sidebar.selectbox(
        "AI 모델 제공자 선택",
        ["G4F", "OpenAI", "Google", "Grok", "Ollama", "Anthropic"],
    )
    return model_provider


def render_api_key_management(model_provider):
    """선택된 제공자에 대한 API 키 관리 UI 렌더링"""
    api_keys = []
    if model_provider != "G4F":
        env_api_key = os.getenv(API_KEY_ENV_VARS.get(model_provider, ""))
        api_keys_key = f"{model_provider}_api_keys"

        st.sidebar.subheader("API 키 관리")

        if api_keys_key not in st.session_state:
            st.session_state[api_keys_key] = env_api_key if env_api_key else ""

        api_keys_text = st.sidebar.text_area(
            f"{model_provider} API 키 목록 (한 줄에 하나씩)",
            value=st.session_state[api_keys_key],
            placeholder="여러 API 키를 한 줄에 하나씩 입력하세요.\\n번역 시 위에서부터 순서대로 사용됩니다.",
            height=150,
            key=f"{model_provider}_api_keys_input",
        )
        st.session_state[api_keys_key] = api_keys_text
        api_keys = [key.strip() for key in api_keys_text.split("\\n") if key.strip()]

        api_keys_col1, api_keys_col2 = st.sidebar.columns(2)

        with api_keys_col1:
            if st.button("API 키 내보내기", key=f"{model_provider}_export_button"):
                if api_keys:
                    api_keys_json = json.dumps(
                        {model_provider: api_keys}, ensure_ascii=False, indent=2
                    )
                    # Use a unique key for the download button to avoid conflicts
                    download_key = (
                        f"{model_provider}_download_button_{int(time.time())}"
                    )
                    st.download_button(
                        label="JSON 파일 다운로드",
                        data=api_keys_json,
                        file_name=f"{model_provider.lower()}_api_keys.json",
                        mime="application/json",
                        key=download_key,
                    )
                else:
                    st.sidebar.warning("내보낼 API 키가 없습니다.")

        with api_keys_col2:
            api_keys_file = st.file_uploader(
                "API 키 가져오기", type=["json"], key=f"{model_provider}_import_file"
            )

            processed_flag_key = f"{model_provider}_api_keys_file_processed"
            current_file_id_key = f"{model_provider}_api_keys_file_id"

            if processed_flag_key not in st.session_state:
                st.session_state[processed_flag_key] = False
            if current_file_id_key not in st.session_state:
                st.session_state[current_file_id_key] = None

            if api_keys_file is not None:
                current_file_identifier = (api_keys_file.name, api_keys_file.size)
                if (
                    not st.session_state[processed_flag_key]
                    or st.session_state[current_file_id_key] != current_file_identifier
                ):
                    try:
                        api_keys_data = json.load(api_keys_file)
                        if model_provider in api_keys_data and isinstance(
                            api_keys_data[model_provider], list
                        ):
                            new_keys_text = "\\n".join(api_keys_data[model_provider])
                            st.session_state[api_keys_key] = new_keys_text
                            st.session_state[processed_flag_key] = True
                            st.session_state[current_file_id_key] = (
                                current_file_identifier
                            )
                            st.sidebar.success(
                                f"{len(api_keys_data[model_provider])}개의 API 키를 가져왔습니다."
                            )
                            st.rerun()  # Rerun to update the text_area
                        else:
                            st.sidebar.warning(
                                f"JSON 파일에 {model_provider} API 키가 없습니다."
                            )
                            st.session_state[processed_flag_key] = False
                            st.session_state[current_file_id_key] = None
                    except Exception as e:
                        st.sidebar.error(f"JSON 파일 로드 오류: {str(e)}")
                        st.session_state[processed_flag_key] = False
                        st.session_state[current_file_id_key] = None
            else:
                # When file is removed, reset the processed state
                if st.session_state.get(processed_flag_key, False):
                    st.session_state[processed_flag_key] = False
                    st.session_state[current_file_id_key] = None
                    st.rerun()  # Rerun to reflect the change

    else:  # G4F Provider
        api_keys = ["g4f-api-key"]  # Dummy key for G4F
        with st.sidebar.container(border=True):
            st.write("⚠️ **G4F 사용 시 주의사항**")
            st.write("""
            - G4F(GPT4Free)는 무료로 GPT 모델을 사용할 수 있게 해주는 오픈소스 프로젝트입니다.
            - :red-background[**공식 OpenAI API가 아니며**], 서드파티 서버를 통해 작동합니다.
            - 다음과 같은 제한사항이 있습니다:
              - 속도 제한이 엄격함
              - 모델 안정성 및 성능이 공식 API보다 낮을 수 있음
              - 장시간 사용 시 IP 차단 가능성 있음
            - 간단한 테스트나 소규모 번역에 적합하며, 대량 작업에는 OpenAI 공식 API 사용을 권장합니다.
            - **무료지만 속도가 아주 느립니다.**
            """)
            st.write("🔗 [G4F GitHub](https://github.com/xtekky/gpt4free)")

    return api_keys


def render_model_selection(model_provider):
    """모델 선택 및 관련 설정 UI 렌더링"""
    selected_model = None
    api_base_url = None
    temperature = 0.0

    if model_provider != "G4F":
        use_custom_model = st.sidebar.checkbox(
            "직접 모델명 입력하기", key=f"{model_provider}_custom_model_check"
        )
        use_custom_api_base = st.sidebar.checkbox(
            "API Base URL 수정하기", key=f"{model_provider}_custom_base_check"
        )
    else:
        use_custom_model = False
        use_custom_api_base = False

    if use_custom_model:
        selected_model = st.sidebar.text_input(
            "모델명 직접 입력", key=f"{model_provider}_model_input"
        )
    else:
        options = MODEL_OPTIONS.get(model_provider, [])
        selected_model = st.sidebar.selectbox(
            "모델 선택", options, key=f"{model_provider}_model_select"
        )

    env_api_base = os.getenv(API_BASE_ENV_VARS.get(model_provider, ""))
    default_api_base = "http://localhost:11434" if model_provider == "Ollama" else ""

    if use_custom_api_base:
        api_base_url = st.sidebar.text_input(
            "API Base URL",
            value=env_api_base if env_api_base else default_api_base,
            key=f"{model_provider}_base_input",
        )
    else:
        # For Ollama, default base URL might still be needed even if not explicitly customized
        if model_provider == "Ollama":
            api_base_url = env_api_base if env_api_base else default_api_base
        else:
            api_base_url = None  # Use default base URL of the provider if not Ollama and not customized

    temperature = st.sidebar.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=0.0,
        step=0.05,
        help="값이 낮을수록 더 창의성이 낮은 응답이, 높을수록 더 창의성이 높은 응답이 생성됩니다. 각 모델별로 제공사(Google, OpenAI)가 추천하는 값이 다름으로 공식 문서를 참고하여 설정하세요.",
        key=f"{model_provider}_temperature_slider",
    )

    return selected_model, api_base_url, temperature


def render_rate_limiter_settings(model_provider):
    """API 속도 제한 설정 UI 렌더링"""
    st.sidebar.subheader("API 속도 제한")
    if model_provider == "G4F":
        use_rate_limiter = True
        rpm = 30
        st.sidebar.markdown("G4F 모드: 속도 제한 고정 (RPM: 30)")
    else:
        use_rate_limiter = st.sidebar.checkbox(
            "API 속도 제한 사용", value=True, key="rate_limiter_checkbox"
        )
        rpm = st.sidebar.number_input(
            "분당 요청 수(RPM)",
            min_value=1,
            max_value=1000,
            value=60,
            step=1,
            disabled=not use_rate_limiter,
            help="분당 최대 API 요청 횟수를 설정합니다. 값이 낮을수록 API 할당량을 절약할 수 있습니다.",
            key="rpm_input",
        )
    return use_rate_limiter, rpm


def render_request_delay_settings(model_provider):
    """요청 딜레이 설정 UI 렌더링"""
    st.sidebar.subheader("요청 딜레이 설정")
    if model_provider == "G4F":
        use_request_delay = True
        request_delay = 1.0
        st.sidebar.markdown("G4F 모드: 요청 딜레이 고정 (1.0초)")
    else:
        use_request_delay = st.sidebar.checkbox(
            "요청 사이 딜레이 사용", value=False, key="request_delay_checkbox"
        )
        request_delay = st.sidebar.number_input(
            "요청 간 딜레이(초)",
            min_value=0.0,
            max_value=10.0,
            value=0.5,
            step=0.1,
            format="%.1f",
            disabled=not use_request_delay,
            help="각 API 요청 사이의 최소 대기 시간을 설정합니다. 값이 높을수록 API 오류가 감소할 수 있지만 번역 속도가 느려집니다.",
            key="request_delay_input",
        )
    return use_request_delay, request_delay


def render_log_settings():
    """로그 설정 UI 렌더링"""
    st.sidebar.subheader("로그 설정")
    max_log_lines = st.sidebar.number_input(
        "최대 로그 라인 수",
        min_value=100,
        max_value=1000,
        value=100,
        step=100,
        key="max_log_lines_input",
    )
    return max_log_lines


def render_custom_dictionary_upload():
    """커스텀 사전 업로드 UI 렌더링"""
    st.sidebar.header("커스텀 사전")
    custom_dict_file = st.sidebar.file_uploader(
        "커스텀 사전 업로드 (JSON)", type=["json"], key="custom_dict_uploader"
    )
    return custom_dict_file


# --- 파일 처리 및 사전 관련 ---


def get_supported_extensions():
    """지원하는 파일 확장자 목록 반환"""
    return BaseParser.get_supported_extensions()


def get_parser_by_extension(extension):
    """파일 확장자에 맞는 파서 클래스 반환"""
    return BaseParser.get_parser_by_extension(extension)


def add_to_dictionary(
    en_value, ko_value, translation_dictionary, translation_dictionary_lowercase
):
    """번역 사전에 항목 추가 (중복 처리 포함)"""
    try:
        en_lower = en_value.lower()
        if en_lower in translation_dictionary_lowercase:
            original_key = translation_dictionary_lowercase[en_lower]
            target = translation_dictionary[original_key]
            if isinstance(target, list):
                if ko_value not in target:
                    target.append(ko_value)
            elif isinstance(target, str):
                if target != ko_value:
                    translation_dictionary[original_key] = [target, ko_value]
            # else: # Log unexpected type if needed
            #     logger.warning(f"Unexpected type in dictionary for key '{original_key}': {type(target)}")
        else:
            translation_dictionary[en_value] = ko_value
            translation_dictionary_lowercase[en_lower] = en_value
    except Exception as e:
        logger.error(f"번역 사전 추가 중 오류: {en_value} -> {ko_value}, Error: {e}")
        logger.debug(traceback.format_exc())
    return translation_dictionary, translation_dictionary_lowercase


def extract_lang_content(file_path, content=None):
    """파일 경로 또는 내용에서 언어 데이터 추출"""
    try:
        if content is None:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

        # Determine file extension
        if isinstance(file_path, str):
            file_ext = os.path.splitext(file_path)[1]
        elif hasattr(file_path, "name"):  # Handle UploadedFile object
            file_ext = os.path.splitext(file_path.name)[1]
        else:
            st.error("알 수 없는 파일 형식입니다.")
            return {}

        parser_class = get_parser_by_extension(file_ext)

        if parser_class:
            return parser_class.load(content)
        else:
            file_identifier = (
                file_path if isinstance(file_path, str) else file_path.name
            )
            st.error(f"지원되지 않는 파일 형식: {file_ext} ({file_identifier})")
            return {}
    except Exception as e:
        file_identifier = (
            file_path
            if isinstance(file_path, str)
            else getattr(file_path, "name", "Unknown File")
        )
        st.error(f"파일 내용 추출 중 오류: {file_identifier}, {str(e)}")
        logger.error(traceback.format_exc())
        return {}


def save_lang_content(original_filename, data):
    """언어 데이터를 문자열로 변환"""
    try:
        file_ext = os.path.splitext(original_filename)[1]
        parser_class = get_parser_by_extension(file_ext)

        if parser_class:
            content = parser_class.save(data)
            return content
        else:
            st.error(f"지원되지 않는 파일 형식: {file_ext}")
            return None
    except Exception as e:
        st.error(f"데이터 저장 형식 변환 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def initialize_translation_dictionary(source_lang_code, target_lang_code):
    """공식 번역 및 커스텀 사전으로 번역 사전을 초기화합니다."""
    translation_dictionary = {}
    translation_dictionary_lowercase = {}

    # 공식 마인크래프트 번역 파일에서 사전 구축 (en_us -> ko_kr 경우만)
    if source_lang_code == "en_us" and target_lang_code == "ko_kr":
        try:
            for key, en_value in OFFICIAL_EN_LANG_FILE.items():
                if key in OFFICIAL_KO_LANG_FILE:
                    ko_value = OFFICIAL_KO_LANG_FILE[key]
                    if en_value and ko_value:  # Ensure both values are not empty
                        add_to_dictionary(
                            en_value,
                            ko_value,
                            translation_dictionary,
                            translation_dictionary_lowercase,
                        )
            logger.info(
                f"공식 마인크래프트 번역 사전 로드 완료: {len(translation_dictionary)}개 항목"
            )
        except Exception as e:
            st.sidebar.warning(f"공식 번역 파일 로드 오류: {str(e)}")
            logger.warning(f"공식 번역 파일 로드 오류: {str(e)}")
    else:
        logger.info(
            f"소스/타겟 언어({source_lang_code}->{target_lang_code}) 조합으로 공식 사전 구축을 건너뜁니다."
        )

    return translation_dictionary, translation_dictionary_lowercase


def load_custom_dictionary(
    custom_dict_file, translation_dictionary, translation_dictionary_lowercase
):
    """업로드된 커스텀 사전 파일을 로드하고 기존 사전에 병합합니다."""
    if custom_dict_file is not None:
        try:
            custom_dict_data = json.load(custom_dict_file)
            added_count = 0
            for en, ko in custom_dict_data.items():
                # Store original state before modification
                original_ko = translation_dictionary.get(en)
                add_to_dictionary(
                    en, ko, translation_dictionary, translation_dictionary_lowercase
                )
                # Check if the dictionary entry was actually new or modified
                if original_ko != translation_dictionary.get(en):
                    added_count += 1

            st.sidebar.success(
                f"커스텀 사전 로드 완료: {added_count}개 항목 추가/수정 (총 {len(translation_dictionary)}개)"
            )
            logger.info(
                f"커스텀 사전 로드 완료: {added_count}개 항목 추가/수정 (총 {len(translation_dictionary)}개)"
            )
        except Exception as e:
            st.sidebar.error(f"커스텀 사전 로드 오류: {str(e)}")
            logger.error(f"커스텀 사전 로드 오류:\n{traceback.format_exc()}")

    return translation_dictionary, translation_dictionary_lowercase


# --- 유틸리티 ---


def get_rate_limiter(use_limiter, rpm):
    """설정에 따라 RateLimiter 인스턴스 생성"""
    if use_limiter:
        rps = rpm / 60.0
        return InMemoryRateLimiter(
            requests_per_second=rps, check_every_n_seconds=0.1, max_bucket_size=10
        )
    return None


def get_delay_manager(use_delay, delay_seconds):
    """설정에 따라 DelayManager 인스턴스 생성"""
    return DelayManager(delay=delay_seconds if use_delay else 0)
