import asyncio
import json
import os
import tempfile

import gradio as gr
from langchain_core.rate_limiters import InMemoryRateLimiter

from gradio_modules.logger import Logger
from minecraft_modpack_auto_translator.delay_manager import DelayManager
from minecraft_modpack_auto_translator.graph import translate_json_file
from minecraft_modpack_auto_translator.parsers.base_parser import BaseParser
from minecraft_modpack_auto_translator.translator import get_translator


def create_file_translator_ui(config_state):
    with gr.Blocks() as file_tab:
        gr.Markdown("## 📄 단일 파일 번역기")
        # 번역 옵션 패널
        with gr.Accordion("번역 옵션", open=True):
            uploaded_file = gr.File(label="번역할 파일 업로드")
            file_split_number = gr.Number(label="파일 분할 작업자 수", value=1)
            use_random_order = gr.Checkbox(label="랜덤 순서로 번역", value=False)

        # UI 요소
        translate_btn = gr.Button("번역 시작")
        progress_label = gr.Label(value="준비 중...")
        progress_bar = gr.Progress(track_tqdm=True)
        log_output = gr.Textbox(label="상세 로그", lines=10, interactive=False)
        download_button = gr.DownloadButton(
            label="💾 번역 결과 다운로드", visible=False
        )

        def start_file_translation(
            uploaded_file,
            file_split_number,
            use_random_order,
            config,
            pr=progress_bar,
        ):
            # Logger 초기화
            logger_client = Logger(config["log_file_path"])
            logger_client.reset_logs()

            def add_log(msg):
                logger_client.write(msg)

            add_log("단일 파일 번역 시작")

            # 모델 설정 로깅
            provider = config.get("provider")
            model_name = config.get("model_name")
            temperature = config.get("temperature")
            add_log(f"모델 설정: {provider}, {model_name}, 온도={temperature}")

            # --- 속도 제한 및 지연 설정 로드 --- #
            use_rate_limiter = config.get("use_rate_limiter", False)
            rpm = config.get("rpm", 60)
            use_request_delay = config.get("use_request_delay", False)
            request_delay = config.get("request_delay", 1.0)

            # Convert RPM to requests per second for InMemoryRateLimiter
            requests_per_second = rpm / 60.0
            rate_limiter = (
                InMemoryRateLimiter(requests_per_second=requests_per_second)
                if use_rate_limiter
                else None
            )
            delay_manager = DelayManager(request_delay) if use_request_delay else None

            if rate_limiter:
                add_log(f"속도 제한 활성화: {requests_per_second:.2f} RPS ({rpm} RPM)")
            if delay_manager:
                add_log(f"요청 지연 활성화: {request_delay}초")
            # --- 설정 로드 끝 --- #

            # 파일 파싱
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            parser = BaseParser.get_parser_by_extension(ext)
            if not parser:
                add_log(f"지원되지 않는 파일 확장자: {ext}")
                return (
                    gr.update(value="파싱 실패"),
                    gr.update(visible=False),
                    logger_client.read_logs(),
                )
            with open(uploaded_file.name, "rb") as f:
                content_bytes = f.read()
            try:
                content_str = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content_str = content_bytes.decode("utf-8", errors="ignore")
            try:
                original_data = parser.load(content_str)
                add_log("파일 파싱 완료")
            except Exception as e:
                add_log(f"파일 파싱 오류: {e}")
                return (
                    gr.update(value="파싱 실패"),
                    gr.update(visible=False),
                    logger_client.read_logs(),
                )

            # 임시 JSON 파일로 저장
            json_input = json.dumps(original_data, ensure_ascii=False, indent=4)
            tmp_in = tempfile.NamedTemporaryFile(
                delete=False, mode="w", encoding="utf-8", suffix=".json"
            )
            tmp_in.write(json_input)
            tmp_in_path = tmp_in.name
            tmp_in.close()
            add_log(f"임시 JSON 입력 파일 생성: {tmp_in_path}")

            # 임시 출력 경로 설정
            tmp_out_dir = tempfile.mkdtemp()
            tmp_out_name = (
                f"translated_{os.path.splitext(os.path.basename(tmp_in_path))[0]}.json"
            )
            tmp_out_path = os.path.join(tmp_out_dir, tmp_out_name)
            add_log(f"임시 JSON 출력 파일 경로: {tmp_out_path}")
            total = len(original_data)
            num = 0
            pr(0, total=total, desc="번역 준비중..")

            async def progress_callback():
                nonlocal num
                num += 1
                pr(num / total, desc="번역 중..")

            # 번역 실행
            try:
                api_keys = config.get("api_keys", [])
                selected_api_key = api_keys[0]
                add_log("단일 파일 번역 시 첫번째 API 키 사용")
                asyncio.run(
                    translate_json_file(
                        input_path=tmp_in_path,
                        output_path=tmp_out_path,
                        custom_dictionary_dict={},
                        llm=get_translator(
                            provider.lower(),
                            selected_api_key,
                            model_name,
                            config.get("api_base"),
                            temperature,
                            # --- RateLimiter 및 DelayManager 전달 --- #
                            rate_limiter=rate_limiter,
                            # --- 전달 끝 --- #
                        ),
                        max_workers=int(file_split_number),
                        use_random_order=use_random_order,
                        delay_manager=delay_manager,
                        progress_callback=progress_callback,
                    )
                )
                add_log("번역 완료")
            except Exception as e:
                add_log(f"번역 중 오류: {e}")
                return (
                    gr.update(value="번역 실패"),
                    gr.update(visible=False),
                    logger_client.read_logs(),
                )
            # 결과 JSON 로드 및 원본 포맷으로 변환
            try:
                with open(tmp_out_path, "r", encoding="utf-8") as f:
                    translated_json = json.load(f)
                translated_content = parser.save(translated_json)
                add_log("원본 형식으로 변환 완료")
            except Exception as e:
                add_log(f"결과 변환 오류: {e}")
                return (
                    gr.update(value="변환 실패"),
                    gr.update(visible=False),
                    logger_client.read_logs(),
                )

            # 임시 파일 정리
            try:
                os.remove(tmp_in_path)
                add_log(f"임시 입력 파일 삭제: {tmp_in_path}")
                import shutil

                shutil.rmtree(tmp_out_dir)
                add_log(f"임시 출력 디렉토리 삭제: {tmp_out_dir}")
            except Exception as e:
                add_log(f"임시 파일 정리 오류: {e}")

            # 최종 번역 파일 저장 및 다운로드 설정
            final_ext = ext
            final_name_prefix = f"{os.path.splitext(uploaded_file.name)[0]}_{os.getenv('LANG_CODE', 'ko_kr')}"
            tmp_final = tempfile.NamedTemporaryFile(
                delete=False,
                mode="w",
                encoding="utf-8",
                suffix=final_ext,
                prefix=final_name_prefix,
            )
            tmp_final.write(translated_content)
            tmp_final_path = tmp_final.name
            tmp_final.close()
            add_log(f"최종 번역 파일 생성: {tmp_final_path}")

            # 결과 반환
            return (
                gr.update(value="번역 완료"),
                gr.update(value=tmp_final_path, visible=True),
                logger_client.read_logs(),
            )

        translate_btn.click(
            start_file_translation,
            inputs=[
                uploaded_file,
                file_split_number,
                use_random_order,
                config_state,
            ],
            outputs=[progress_label, download_button],
        )

        def update_log(config):
            log_file_path = config.get("log_file_path")
            if log_file_path:
                logger_client = Logger(log_file_path)
                return gr.update(value=logger_client.read_logs())

        gr.Timer(3).tick(fn=update_log, inputs=[config_state], outputs=log_output)
    return file_tab
