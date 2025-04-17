import asyncio
import json
import logging
import os
import sys
import time
import traceback

import streamlit as st
from annotated_text import annotated_text

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

    # translation_dictionary_lowercase 는 현재 코드에서 직접 사용되지 않으므로 필요시 생성

    input_text = st.text_area(
        "번역할 텍스트를 입력하세요:", height=200, key="input_text_area"
    )
    translated_text_area = st.empty()  # 번역 결과 표시 영역

    # 번역 실행 버튼
    if st.button("번역 시작", key="translate_button"):
        # --- 사전 초기화 및 로드 ---
        # 공식 사전 로드
        official_dict, official_dict_lower = initialize_translation_dictionary(
            source_lang_code, target_lang_code
        )
        # 사용자 지정 사전 로드 (빈 사전을 기반으로 로드)
        custom_dict, custom_dict_lower = load_custom_dictionary(
            custom_dict_file, {}, {}
        )

        # 번역 컨텍스트 및 다운로드용 병합 사전 생성
        translation_dictionary = official_dict.copy()
        translation_dictionary.update(custom_dict)

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

        # 로깅 핸들러 설정
        log_handler = setup_logging(max_log_lines=max_log_lines)

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

                # 공유 컨텍스트 생성 (병합된 사전 전달)
                shared_context = TranslationContext(
                    translation_graph=translation_graph,
                    custom_dictionary_dict=translation_dictionary,  # 병합된 사전 사용
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
                    # --- 새로운 2단계 강조 표시 로직 ---
                    def find_matches(dictionary, text, tag):
                        """주어진 사전의 값들을 텍스트에서 찾아 (시작, 끝, 태그) 리스트 반환"""
                        matches = []
                        text_lower = text.lower()
                        for value in dictionary.values():
                            values_to_search = []
                            if isinstance(value, str):
                                if len(value) > 1:  # 1글자 단어는 제외
                                    values_to_search.append(value)
                            elif isinstance(value, list):
                                values_to_search.extend(
                                    [
                                        item
                                        for item in value
                                        if isinstance(item, str) and len(item) > 1
                                    ]  # 1글자 단어는 제외
                                )

                            for val_str in values_to_search:
                                val_str_lower = val_str.lower()
                                if not val_str_lower:
                                    continue
                                start_index = 0
                                while True:
                                    index = text_lower.find(val_str_lower, start_index)
                                    if index == -1:
                                        break
                                    end_index = index + len(val_str_lower)
                                    # 원본 텍스트 조각과 태그 저장
                                    original_text_segment = text[index:end_index]
                                    matches.append(
                                        (index, end_index, tag, original_text_segment)
                                    )
                                    start_index = index + 1
                        return matches

                        # 2단계: 사용자 정의 사전 매칭

                    temp_dict = shared_context.get_dictionary()
                    out = {}

                    for k, i in temp_dict.items():
                        if k not in official_dict:  # 공식 사전에 없는 키만 처리
                            if isinstance(i, list):
                                out[k] = [item for item in i if isinstance(item, str)]
                            else:
                                out[k] = i

                    custom_matches = find_matches(out, translated_text, "추가 사전")

                    # 1단계: 공식 사전 매칭
                    official_matches = find_matches(
                        official_dict, translated_text, "공식 사전"
                    )

                    # 모든 매치 결합
                    all_matches = custom_matches + official_matches

                    filtered_matches = []
                    if all_matches:
                        # 정렬: 시작 위치 오름차순, 길이(end-start) 내림차순
                        all_matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))

                        # --- 수정된 필터링 로직 --- #
                        processed_indices = set()
                        temp_filtered_matches = []  # 임시 리스트

                        for start, end, tag, segment in all_matches:
                            # 현재 매치가 이미 처리된 인덱스와 겹치는지 확인
                            is_overlapping = False
                            for i in range(start, end):
                                if i in processed_indices:
                                    is_overlapping = True
                                    break

                            # 겹치지 않는 경우에만 추가 (정렬 순서상 먼저 오는 것이 더 길거나 같음)
                            if not is_overlapping:
                                temp_filtered_matches.append((start, end, tag, segment))
                                # 이 매치가 차지하는 인덱스를 기록
                                for i in range(start, end):
                                    processed_indices.add(i)

                        # 최종 결과를 위해 시작 위치 기준으로 다시 정렬
                        temp_filtered_matches.sort(key=lambda x: x[0])
                        filtered_matches = temp_filtered_matches
                        # --- 필터링 로직 수정 끝 --- #

                    # annotated_result 구성
                    annotated_result = []
                    current_pos = 0
                    for start, end, tag, segment in filtered_matches:
                        if start > current_pos:
                            annotated_result.append(translated_text[current_pos:start])
                        # 태그와 함께 매치된 부분 추가 (여기서 segment 사용)
                        annotated_result.append((segment, tag))
                        current_pos = end

                    if current_pos < len(translated_text):
                        annotated_result.append(translated_text[current_pos:])

                    if not annotated_result:  # 매치된 것이 없으면 원본 텍스트
                        annotated_result = [translated_text]

                    # 이번 번역에서 추가된 사전 항목 출력
                    if out:
                        st.subheader("🆕 이번 번역에서 추가된 사전 항목")
                        cols = st.columns(4)  # 4열 그리드 생성
                        for i, (key, value) in enumerate(out.items()):
                            st.write(f"`{key}` → `{value}`")
                    else:
                        st.info("ℹ️ 이번 번역에서 새로 추가된 사전 항목이 없습니다.")
                    st.subheader("🎯 번역 결과")
                    st.caption(
                        "※ 아래 사전 항목들은 임의로 표시되는 방식일 뿐이며, 실제 번역에 사용된 사전과는 무관할 수 있습니다."
                    )
                    # 최종 결과 표시
                    annotated_text(annotated_result)
                    # --- 강조 표시 로직 끝 ---

                    # 다운로드 버튼 (컨텍스트에서 업데이트된 병합 사전 사용)
                    updated_dict_to_download = shared_context.get_dictionary()
                    if updated_dict_to_download:
                        updated_dict_json = json.dumps(
                            updated_dict_to_download, ensure_ascii=False, indent=4
                        )
                        st.download_button(
                            label=f"📚 업데이트된 사전 다운로드 ({len(updated_dict_to_download)}개 항목)",
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
