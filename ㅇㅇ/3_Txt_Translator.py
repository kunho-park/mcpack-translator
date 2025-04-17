import asyncio
import json
import logging
import os
import sys
import time
import traceback

import streamlit as st

# Windows 환경에서 asyncio 이벤트 루프 정책 설정
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# import minecraft_modpack_auto_translator # 이제 직접 사용하지 않음
from minecraft_modpack_auto_translator.graph import (
    create_translation_graph,
    registry,
)
from minecraft_modpack_auto_translator.loaders.context import TranslationContext
from minecraft_modpack_auto_translator.translator import get_translator
from streamlit_utils import (
    get_rate_limiter,
    initialize_translation_dictionary,
    load_custom_dictionary,
    render_api_key_management,
    render_custom_dictionary_upload,
    render_log_settings,
    render_model_provider_selection,
    render_model_selection,
    render_rate_limiter_settings,
    setup_logging,
)

st.set_page_config(
    page_title="텍스트 번역기",
    page_icon="✏️",
    layout="wide",
)

logger = logging.getLogger(__name__)
# 디버그 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# 언어 코드 설정 (기본값)
LANG_CODE = os.getenv("LANG_CODE", "ko_kr")


def main():
    st.title("✏️ 텍스트 번역기")
    st.markdown("입력한 텍스트를 원하는 언어로 번역합니다.")

    if "api_key_index" not in st.session_state:
        st.session_state.api_key_index = 0

    # --- 사이드바 설정 ---
    st.sidebar.header("⚙️ 번역 설정")

    model_provider = render_model_provider_selection()
    api_keys = render_api_key_management(model_provider)
    selected_model, api_base_url, temperature = render_model_selection(model_provider)
    use_rate_limiter, rpm = render_rate_limiter_settings(model_provider)

    max_log_lines = render_log_settings()
    custom_dict_file = render_custom_dictionary_upload()
    # --- End Sidebar Settings ---

    # --- 메인 화면 ---
    col1, col2 = st.columns(2)
    with col1:
        source_lang_code = st.text_input(
            "원본 언어 코드",
            "en_us",
            placeholder="번역할 원본 언어 코드를 입력하세요 (예: en_us)",
            key="source_lang_input",  # 키 추가
        ).lower()  # 입력값을 소문자로 변환
    # target_lang_code는 고정
    target_lang_code = LANG_CODE

    # 사전 초기화 및 로드
    translation_dictionary, translation_dictionary_lowercase = (
        initialize_translation_dictionary(source_lang_code, target_lang_code)
    )
    translation_dictionary, translation_dictionary_lowercase = load_custom_dictionary(
        custom_dict_file, translation_dictionary, translation_dictionary_lowercase
    )

    input_text = st.text_area(
        "번역할 텍스트를 입력하세요:", height=200, key="input_text_area"
    )
    translated_text_area = st.empty()  # 번역 결과 표시 영역

    # 번역 실행 버튼
    if st.button("번역 시작", key="translate_button"):
        if not api_keys and model_provider != "G4F":
            st.error("API 키를 입력해주세요.")
            st.stop()

        if not input_text:
            st.error("번역할 텍스트를 입력해주세요.")
            st.stop()

        if not target_lang_code:
            # 이 부분은 LANG_CODE를 사용하므로 실제로는 발생하기 어려움
            st.error(
                "대상 언어 코드가 설정되지 않았습니다. 환경 변수 LANG_CODE를 확인하세요."
            )
            st.stop()

        # 로깅 핸들러 설정 및 UI 표시 (수정/추가된 부분)
        log_session_key = "text_translator_logs"  # 파일별 고유 키
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
            if st.button("로그 지우기", key="clear_log_button_text"):  # 버튼 키 추가
                if log_handler:
                    log_handler.clear_logs()
                    st.rerun()
        # --- 로깅 UI 추가 끝 ---

        try:
            with st.spinner("번역 진행 중..."):
                status_text = st.empty()
                status_text.text("모델 초기화 및 번역 준비 중...")
                logger.info("번역 프로세스 시작...")

                st.session_state.api_key_index = 0
                total_api_keys = len(api_keys) if api_keys else 1
                logger.info(f"총 {total_api_keys}개의 API 키를 순차적으로 사용합니다.")

                # Rate Limiter 및 Delay Manager 생성
                rate_limiter = get_rate_limiter(
                    use_rate_limiter and model_provider != "G4F", rpm
                )
                if rate_limiter:
                    logger.info(f"속도 제한 설정: {rpm} RPM ({rpm / 60.0:.2f} RPS)")

                # 번역 그래프 생성
                translation_graph = create_translation_graph()

                # 공유 컨텍스트 생성
                shared_context = TranslationContext(
                    translation_graph=translation_graph,  # 생성된 그래프 전달
                    custom_dictionary_dict=translation_dictionary,
                    registry=registry,
                )
                shared_context.initialize_dictionaries()
                dict_len = len(shared_context.get_dictionary())
                logger.info(f"번역 컨텍스트 생성 완료: {dict_len}개 사전 항목")

                start_time = time.time()

                async def translate_text_async():
                    nonlocal translation_dictionary  # 사전 업데이트를 위해 nonlocal 선언
                    try:
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

                        translator = get_translator(
                            provider=model_provider.lower(),
                            api_key=current_api_key,
                            model_name=selected_model,
                            api_base=api_base_url,
                            temperature=temperature,
                            rate_limiter=rate_limiter,
                        )

                        status_text.text("텍스트 번역 중...")
                        logger.info(f"입력 텍스트 번역 시작 (모델: {selected_model})")

                        # --- translate_dict 호출 대신 graph.ainvoke 사용 --- #
                        # 번역 그래프 실행
                        state = await translation_graph.ainvoke(
                            {
                                "text": input_text,
                                "custom_dictionary_dict": shared_context.get_dictionary(),
                                "llm": translator,
                                "context": shared_context,
                                # graph 실행에 필요한 추가 파라미터가 있다면 여기 추가
                                # 예: "source_lang_code": source_lang_code,
                                # 예: "target_lang_code": target_lang_code,
                            },
                        )

                        # 결과 텍스트 추출 (graph의 최종 상태 스키마에 따라 달라질 수 있음)
                        # 'restored_text' 가 최종 번역 결과라고 가정
                        result_text = state.get(
                            "restored_text", "번역 결과를 찾을 수 없습니다."
                        )
                        # ----------------------------------------------------- #

                        end_time = time.time()
                        elapsed_time = end_time - start_time
                        logger.info(
                            f"텍스트 번역 완료. 소요 시간: {elapsed_time:.2f}초"
                        )
                        status_text.text(
                            f"번역 완료! (소요 시간: {elapsed_time:.2f}초)"
                        )

                        translation_dictionary = (
                            shared_context.get_dictionary()
                        )  # 업데이트된 사전 가져오기
                        return result_text

                    except Exception as e:
                        logger.error(f"텍스트 번역 중 오류: {str(e)}")
                        logger.error(traceback.format_exc())
                        st.error(f"번역 중 오류가 발생했습니다: {str(e)}")
                        status_text.error("번역 중 오류 발생.")
                        return None

                translated_text = asyncio.run(translate_text_async())

                if translated_text:
                    st.subheader("🎯 번역 결과")
                    translated_text_area.text_area(
                        "번역 결과:",
                        translated_text,
                        height=200,
                        key="translated_text_output",
                    )

                    if translation_dictionary:
                        updated_dict_json = json.dumps(
                            translation_dictionary, ensure_ascii=False, indent=4
                        )
                        st.download_button(
                            label=f"📚 업데이트된 사전 다운로드 ({len(translation_dictionary)}개 항목)",
                            data=updated_dict_json.encode("utf-8"),
                            file_name=f"updated_dictionary_{target_lang_code}.json",
                            mime="application/json",
                            key="download_dict_button",
                        )

        except Exception as e:
            st.error(f"번역 프로세스 중 오류 발생: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
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
