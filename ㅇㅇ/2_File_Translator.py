import asyncio
import json
import logging
import os
import sys
import tempfile  # 임시 파일 생성을 위해 추가
import time
import traceback

import streamlit as st

# Windows 환경에서 asyncio 이벤트 루프 정책 설정
if sys.platform.startswith("win"):
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from minecraft_modpack_auto_translator import (  # translate_json_file 임포트 추가
    translate_json_file,
)
from minecraft_modpack_auto_translator.graph import (
    create_translation_graph,
    registry,
)
from minecraft_modpack_auto_translator.loaders.context import (
    TranslationContext,
)
from minecraft_modpack_auto_translator.translator import get_translator
from streamlit_utils import (
    get_delay_manager,
    get_rate_limiter,
    get_supported_extensions,
    initialize_translation_dictionary,
    load_custom_dictionary,
    render_api_key_management,
    render_custom_dictionary_upload,
    render_log_settings,
    render_model_provider_selection,
    render_model_selection,
    render_rate_limiter_settings,
    render_request_delay_settings,
    setup_logging,
)


def get_parser_by_extension(extension):
    """파일 확장자에 맞는 파서 클래스를 반환합니다."""
    from minecraft_modpack_auto_translator.parsers.base_parser import BaseParser

    return BaseParser.get_parser_by_extension(extension)


st.set_page_config(
    page_title="단일 파일 번역기",
    page_icon="📄",
    layout="wide",
)

logger = logging.getLogger(__name__)
# 디버그 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# 언어 코드 설정
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


def main():
    st.title("📄 단일 파일 번역기")
    st.markdown("JSON, LANG, SNBT 형식의 단일 언어 파일을 번역합니다.")

    if "api_key_index" not in st.session_state:
        st.session_state.api_key_index = 0

    st.sidebar.header("번역 설정")

    model_provider = render_model_provider_selection()
    api_keys = render_api_key_management(model_provider)
    selected_model, api_base_url, temperature = render_model_selection(model_provider)
    use_rate_limiter, rpm = render_rate_limiter_settings(model_provider)
    use_request_delay, request_delay = render_request_delay_settings(model_provider)

    # 병렬 처리 설정 (파일 내부) - File Translator Specific
    st.sidebar.subheader("병렬 처리 설정 (파일 내부)")
    if model_provider == "G4F":
        file_split_number = 3
        st.sidebar.markdown("G4F 모드: 파일 분할 작업자 수 고정 (3개)")
    else:
        file_split_number = st.sidebar.number_input(
            "파일 분할 작업자 수",
            min_value=1,
            max_value=100,
            value=1,
            step=1,
            help="파일 내부의 번역 항목을 몇 개의 작업으로 분할하여 동시에 처리할지 설정합니다. 값이 높을수록 단일 파일 번역 속도가 빨라질 수 있지만, API 사용량이 늘어납니다.",
            key="file_split_number_input",
        )

    use_random_order = st.sidebar.checkbox(
        "랜덤 순서로 번역",
        value=False,
        help="파일 내부 항목을 랜덤 순서로 번역하여 병렬 번역 시 사전의 정확도를 높입니다.",
        key="random_order_checkbox",
    )

    max_log_lines = render_log_settings()
    custom_dict_file = render_custom_dictionary_upload()
    # --- End Sidebar Settings ---

    # --- 메인 화면 ---
    col1, col2 = st.columns(2)
    with col1:
        source_lang_code = st.text_input(
            "원본 언어 코드", "en_us", key="source_lang_input"
        ).lower()

    supported_extensions = get_supported_extensions()
    uploaded_file = st.file_uploader(
        f"번역할 언어 파일 업로드 ({', '.join(supported_extensions)})",
        type=[ext.lstrip(".") for ext in supported_extensions],
        key="file_uploader",
    )

    target_lang_code = LANG_CODE
    # 사전 초기화 및 로드 (streamlit_utils 사용)
    translation_dictionary, translation_dictionary_lowercase = (
        initialize_translation_dictionary(source_lang_code, target_lang_code)
    )
    translation_dictionary, translation_dictionary_lowercase = load_custom_dictionary(
        custom_dict_file, translation_dictionary, translation_dictionary_lowercase
    )

    # 번역 실행 버튼
    if st.button("번역 시작"):
        if not api_keys and model_provider != "G4F":
            st.error("API 키를 입력해주세요.")
            st.stop()

        if uploaded_file is None:
            st.error("번역할 파일을 업로드해주세요.")
            st.stop()

        # 로깅 핸들러 설정 및 UI 표시 (수정/추가된 부분)
        log_session_key = "file_translator_logs"  # 파일별 고유 키
        log_handler = setup_logging(
            max_log_lines=max_log_lines, session_key=log_session_key
        )

        # 로그 세션 상태 키 명시적 초기화 (KeyError 방지)
        if log_session_key not in st.session_state:
            st.session_state[log_session_key] = []

        # 로그를 표시할 UI 영역 생성
        log_container = st.expander("번역 로그", expanded=True)
        with log_container:
            log_messages_to_display = st.session_state[log_session_key]
            log_area = st.markdown(
                "  \n".join(log_messages_to_display), unsafe_allow_html=True
            )
            if st.button("로그 지우기", key="clear_log_button_file"):  # 버튼 키 추가
                if log_handler:
                    log_handler.clear_logs()
                    st.rerun()

        try:
            with st.spinner("번역 진행 중..."):
                st.subheader("번역 진행 상황")
                progress_bar = st.progress(0)
                progress_text = st.empty()
                status_text = st.empty()

                status_text.text("모델 초기화 중...")
                logger.info("모델 초기화 중...")

                st.session_state.api_key_index = 0
                total_api_keys = len(api_keys) if api_keys else 1
                logger.info(f"총 {total_api_keys}개의 API 키를 순차적으로 사용합니다.")

                # Rate Limiter 및 Delay Manager 생성 (streamlit_utils 사용)
                rate_limiter = get_rate_limiter(
                    use_rate_limiter and model_provider != "G4F", rpm
                )
                if rate_limiter:
                    logger.info(f"속도 제한 설정: {rpm} RPM ({rpm / 60.0:.2f} RPS)")

                g4f_delay = 1.0 if model_provider == "G4F" else 0
                effective_delay = (
                    request_delay
                    if use_request_delay and model_provider != "G4F"
                    else g4f_delay
                )
                delay_manager = get_delay_manager(effective_delay > 0, effective_delay)
                if effective_delay > 0:
                    logger.info(f"요청 딜레이 설정: {effective_delay:.1f}초")

                # 공유 컨텍스트 생성 (기존 로직 유지)
                shared_context = TranslationContext(
                    translation_graph=create_translation_graph(),
                    custom_dictionary_dict=translation_dictionary,
                    registry=registry,
                )
                shared_context.initialize_dictionaries()
                dict_len = len(shared_context.get_dictionary())
                logger.info(f"번역 컨텍스트 생성 완료: {dict_len}개 사전 항목")

                # 파일 내용 읽기 (기존 로직 유지)
                file_content_bytes = uploaded_file.getvalue()
                try:
                    file_content_str = file_content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    st.error("파일 인코딩 오류: UTF-8 형식의 파일만 지원합니다.")
                    st.stop()

                # 입력 데이터 파싱 (streamlit_utils 사용 -> 이제 translate_json_file이 처리)
                # input_data = extract_lang_content(uploaded_file, file_content_str)
                # if not isinstance(input_data, dict):
                #     st.error(
                #         "파일 내용을 파싱할 수 없습니다. 지원되는 형식(JSON, LANG, SNBT)인지 확인해주세요."
                #     )
                #     st.stop()

                start_time = time.time()
                # total_items 는 translate_single_file 내에서 계산하도록 변경
                # processed_items = 0

                async def update_progress(
                    done=False, total_items=None, processed_items=None
                ):
                    # nonlocal processed_items -> 이 함수는 이제 worker 콜백으로 사용되지 않음
                    current_time = time.time()
                    progress_percent = 0
                    items_info = ""

                    if total_items is not None and processed_items is not None:
                        progress_percent = (
                            int((processed_items / total_items) * 95)
                            if total_items > 0 and not done
                            else 100
                        )
                        items_info = f"**{processed_items}/{total_items}** 항목 "

                    progress_bar.progress(progress_percent)
                    progress_text.markdown(f"{items_info}({progress_percent}%) ")

                    elapsed_time = current_time - start_time
                    hours, rem = divmod(elapsed_time, 3600)
                    mins, secs = divmod(rem, 60)
                    elapsed_str = f"{int(hours):02}:{int(mins):02}:{int(secs):02}"

                    status_msg = (
                        f"번역 완료! 총 경과 시간: {elapsed_str}"
                        if done
                        else f"번역 중... 경과 시간: {elapsed_str}"
                    )
                    status_text.markdown(status_msg)

                # translate_json_file 내부 콜백 함수
                processed_items_count = 0
                total_items_count = 0

                async def worker_progress_callback():
                    nonlocal processed_items_count, total_items_count
                    if total_items_count > 0:
                        processed_items_count = min(
                            processed_items_count + 1, total_items_count - 1
                        )
                        await update_progress(
                            done=False,
                            total_items=total_items_count,
                            processed_items=processed_items_count,
                        )

                async def translate_single_file():
                    nonlocal \
                        translation_dictionary, \
                        processed_items_count, \
                        total_items_count
                    temp_input_file = None
                    translated_data_dict = None  # 결과 딕셔너리
                    translated_content_str = None  # 결과 문자열
                    try:
                        # 원본 파일 내용으로 임시 입력 파일 생성
                        with tempfile.NamedTemporaryFile(
                            delete=False,
                            mode="w",
                            encoding="utf-8",
                            suffix=os.path.splitext(uploaded_file.name)[1],
                        ) as tmp_f:
                            # 원본 파서를 사용하여 원본 내용을 한번 파싱하고 다시 저장 (정규화 목적)
                            try:
                                file_ext = os.path.splitext(uploaded_file.name)[
                                    1
                                ].lower()
                                parser = get_parser_by_extension(file_ext)
                                if parser:
                                    original_data = parser.load(file_content_str)
                                    # total_items_count 설정
                                    if isinstance(original_data, dict):
                                        total_items_count = len(original_data)
                                    # 원본 파일 형식으로 다시 저장
                                    normalized_content = parser.save(original_data)
                                    tmp_f.write(normalized_content)
                                else:
                                    # 파서 없으면 원본 그대로 사용
                                    tmp_f.write(file_content_str)
                                    # 원본 내용을 기반으로 대략적인 항목 수 계산 (JSON, LANG만)
                                    if file_ext == ".json":
                                        try:
                                            total_items_count = len(
                                                json.loads(file_content_str)
                                            )
                                        except json.JSONDecodeError:
                                            total_items_count = (
                                                file_content_str.count("\n") + 1
                                            )
                                    elif file_ext in [".lang", ".txt"]:
                                        total_items_count = (
                                            file_content_str.count("\n") + 1
                                        )
                                    else:
                                        total_items_count = 1  # 알 수 없을 때 기본값

                            except Exception as parse_err:
                                logger.warning(
                                    f"원본 파일 정규화 중 오류: {parse_err}, 원본 내용 그대로 사용합니다."
                                )
                                tmp_f.write(file_content_str)
                                # 원본 내용을 기반으로 대략적인 항목 수 계산 (JSON, LANG만)
                                file_ext = os.path.splitext(uploaded_file.name)[
                                    1
                                ].lower()
                                if file_ext == ".json":
                                    try:
                                        total_items_count = len(
                                            json.loads(file_content_str)
                                        )
                                    except json.JSONDecodeError:
                                        total_items_count = (
                                            file_content_str.count("\n") + 1
                                        )
                                elif file_ext in [".lang", ".txt"]:
                                    total_items_count = file_content_str.count("\n") + 1
                                else:
                                    total_items_count = 1  # 알 수 없을 때 기본값

                            temp_input_file = tmp_f.name
                        logger.info(f"임시 입력 파일 생성: {temp_input_file}")

                        # 임시 출력 파일 경로 생성 (JSON으로 저장될 예정)
                        temp_output_dir = tempfile.mkdtemp()
                        temp_output_file = os.path.join(
                            temp_output_dir,
                            f"translated_{os.path.splitext(uploaded_file.name)[0]}.json",
                        )  # 확장자 .json
                        logger.info(f"임시 출력 파일 경로: {temp_output_file}")

                        current_api_key_index = st.session_state.api_key_index
                        current_api_key = (
                            api_keys[current_api_key_index % total_api_keys]
                            if api_keys
                            else None
                        )

                        st.session_state.api_key_index = (
                            (current_api_key_index + 1) % total_api_keys
                            if api_keys and total_api_keys > 0
                            else 0
                        )

                        logger.info(
                            f"API 키 사용 중: {current_api_key_index + 1}/{total_api_keys}"
                        )

                        processed_items_count = 0  # 콜백용 카운터 초기화
                        # translate_dict 대신 translate_json_file 호출
                        final_dictionary = await translate_json_file(  # 함수 이름 변경 및 인자 수정
                            input_path=temp_input_file,
                            output_path=temp_output_file,  # 출력 경로 추가 (JSON으로 저장됨)
                            custom_dictionary_dict=shared_context.get_dictionary(),
                            llm=get_translator(
                                provider=model_provider.lower(),
                                api_key=current_api_key,
                                model_name=selected_model,
                                api_base=api_base_url,
                                temperature=temperature,
                                rate_limiter=rate_limiter,
                            ),
                            max_workers=file_split_number,
                            progress_callback=worker_progress_callback,  # 내부 콜백 함수 사용
                            external_context=shared_context,
                            delay_manager=delay_manager,
                            use_random_order=use_random_order,
                            # target_lang_code 는 translate_json_file 에 없음
                        )

                        translation_dictionary = final_dictionary  # 최종 사전 업데이트

                        # 번역된 JSON 파일 내용 읽고 원본 형식으로 변환
                        if os.path.exists(temp_output_file):
                            with open(temp_output_file, "r", encoding="utf-8") as f:
                                translated_json_content = f.read()

                            # JSON 파싱
                            try:
                                translated_data_dict = json.loads(
                                    translated_json_content
                                )
                            except json.JSONDecodeError as json_err:
                                logger.error(f"번역 결과 JSON 파싱 오류: {json_err}")
                                st.error(
                                    f"번역 결과 파일(JSON)을 파싱하는 중 오류가 발생했습니다: {json_err}"
                                )
                                raise  # 오류 발생 시 함수 중단

                            # 원본 파일 확장자에 맞는 파서 가져오기
                            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                            parser = get_parser_by_extension(file_ext)

                            if parser:
                                # 파서를 사용하여 원본 형식의 문자열로 변환
                                translated_content_str = parser.save(
                                    translated_data_dict
                                )
                            else:
                                logger.warning(
                                    f"지원되지 않는 파일 확장자({file_ext})의 결과 파서 없음. JSON 내용을 그대로 사용합니다."
                                )
                                # 파서가 없으면 JSON 문자열을 그대로 사용 (다운로드용)
                                translated_content_str = translated_json_content

                        else:
                            logger.error(
                                f"번역 결과 파일({temp_output_file})을 찾을 수 없습니다."
                            )
                            st.error("번역 결과 파일이 생성되지 않았습니다.")
                            raise FileNotFoundError(
                                "Translated file not found"
                            )  # 오류 발생 시 함수 중단

                        await update_progress(
                            done=True,
                            total_items=total_items_count,
                            processed_items=total_items_count,
                        )  # 최종 완료 업데이트

                        # 결과 반환 (딕셔너리, 문자열)
                        return translated_data_dict, translated_content_str

                    except Exception as e:
                        logger.error(f"파일 번역 중 오류: {str(e)}")
                        logger.error(traceback.format_exc())
                        st.error(f"번역 중 오류가 발생했습니다: {str(e)}")
                        await update_progress(
                            done=True,
                            total_items=total_items_count,
                            processed_items=processed_items_count,
                        )  # 오류 시에도 완료 처리
                        return None, None  # 오류 시 None 반환
                    finally:
                        # 임시 파일 및 디렉토리 삭제
                        if temp_input_file and os.path.exists(temp_input_file):
                            try:
                                os.remove(temp_input_file)
                                logger.info(f"임시 입력 파일 삭제: {temp_input_file}")
                            except Exception as e:
                                logger.warning(f"임시 입력 파일 삭제 실패: {e}")
                        if "temp_output_dir" in locals() and os.path.exists(
                            temp_output_dir
                        ):
                            try:
                                import shutil

                                shutil.rmtree(temp_output_dir)
                                logger.info(
                                    f"임시 출력 디렉토리 삭제: {temp_output_dir}"
                                )
                            except Exception as e:
                                logger.warning(f"임시 출력 디렉토리 삭제 실패: {e}")

                # 비동기 함수 실행 및 결과 받기
                translated_data_dict, translated_content_for_download = asyncio.run(
                    translate_single_file()
                )

                if (
                    translated_data_dict and translated_content_for_download
                ):  # 두 결과 모두 정상일 때
                    st.subheader("🎯 번역 결과")

                    # translated_content_for_download 를 직접 사용
                    if translated_content_for_download:
                        translated_filename = f"{os.path.splitext(uploaded_file.name)[0]}_{target_lang_code}{os.path.splitext(uploaded_file.name)[1]}"
                        st.download_button(
                            label=f"💾 번역된 파일 다운로드 ({translated_filename})",
                            data=translated_content_for_download.encode(
                                "utf-8"
                            ),  # 여기서 인코딩
                            file_name=translated_filename,
                            mime="text/plain",
                            key="download_translated_button",
                        )
                    else:
                        st.warning(
                            "번역 결과는 생성되었으나 다운로드용 문자열 변환에 실패했습니다."
                        )

                    if translation_dictionary:
                        updated_dict_json = json.dumps(
                            translation_dictionary, ensure_ascii=False, indent=4
                        )
                        st.download_button(
                            label=f"📚 업데이트된 사전 다운로드 ({len(translation_dictionary)}개 항목)",
                            data=updated_dict_json.encode("utf-8"),
                            file_name="updated_dictionary.json",
                            mime="application/json",
                            key="download_dict_button",
                        )

                    st.success("파일 번역이 완료되었습니다!")
                elif (
                    translated_data_dict is None
                    and translated_content_for_download is None
                ):
                    # translate_single_file 에서 이미 오류 처리 및 메시지 표시됨
                    st.info("번역 과정에서 오류가 발생하여 결과를 표시할 수 없습니다.")
                else:
                    # 예상치 못한 경우 (한쪽만 None)
                    st.error("번역 결과 처리 중 예기치 않은 오류가 발생했습니다.")

        except Exception as e:
            st.error(f"번역 프로세스 중 오류 발생: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            # Log handler removal
            if "log_handler" in locals() and log_handler:
                try:
                    root_logger = logging.getLogger()
                    if log_handler in root_logger.handlers:
                        root_logger.removeHandler(log_handler)
                    modpack_logger = logging.getLogger(
                        "minecraft_modpack_auto_translator"
                    )
                    if log_handler in modpack_logger.handlers:
                        modpack_logger.removeHandler(log_handler)
                except Exception as e:
                    logger.warning(f"로그 핸들러 제거 중 오류: {e}")


if __name__ == "__main__":
    main()
