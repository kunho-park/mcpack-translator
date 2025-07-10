import asyncio
import json
import os
import tempfile
import time
import zipfile

import gradio as gr
import requests
from apscheduler.schedulers.background import BackgroundScheduler

import minecraft_modpack_auto_translator
from gradio_modules.dictionary_builder import (
    process_modpack_directory,
    restore_zip_files,
)
from gradio_modules.logger import Logger
from gradio_modules.translator import run_json_translation
from minecraft_modpack_auto_translator.resourcepack import create_resourcepack

# 스케줄러 초기화 및 시작
scheduler = BackgroundScheduler()
scheduler.start()

HOW_TO_APPLY_PATCH = open("./how_to_apply_patch.md", "r", encoding="utf-8").read()


# 임시 파일 삭제 함수
def delete_file_later(file_path):
    try:
        os.remove(file_path)
        print(f"임시 파일 삭제 완료: {file_path}")
    except OSError as e:
        print(f"임시 파일 삭제 오류 ({file_path}): {e}")


def create_modpack_translator_ui(config_state):
    with gr.Blocks() as tab:
        gr.Markdown("## 🌐 원클릭 모드팩 번역기")
        with gr.Accordion("📖 사용 설명서 (클릭하여 펼치기)", open=False):
            gr.Markdown("""
            ### 🌟 AI 모드팩 번역기 사용 가이드
            
            **📌 기본 사용법:**
            1. 모드팩 ZIP 파일을 업로드하세요
            2. (선택) 기존 번역본이나 커스텀 사전 파일을 업로드할 수 있습니다
            3. 번역 옵션을 설정한 후 '번역 시작' 버튼을 클릭하세요
            4. 번역이 완료되면 결과 ZIP 파일을 다운로드 받으세요
            
            **⚙️ 주요 기능 설명:**
            - **기존 번역에서 사전 자동 구축**: 기존 번역 파일을 분석하여 번역 품질 향상
            - **이미 번역된 파일 건너뛰기**: 중복 작업 방지
            - **Config/KubeJS/Mods 파일 번역**: 다양한 파일 유형 선택적 번역 지원
            - **동시 작업자 수**: 병렬 처리로 번역 속도 조절 가능
            
            **📚 자세한 설명은 [공식 문서](https://kunho-park.notion.site/AI-mcpack-translator-1dc8edfca9988073a109f2b746f1aa8d) 참조**
            
            **⚠️ 주의사항:**
            - 대용량 모드팩의 경우 시간이 오래 걸릴 수 있습니다
            - 번역 품질을 높이려면 커스텀 사전 사용을 권장합니다
            - 오류 발생 시 로그를 확인해주세요
            """)
        with gr.Row():
            with gr.Column(scale=1, min_width=300):
                with gr.Accordion("번역 옵션", open=True):
                    source_lang = gr.Textbox(label="원본 언어 코드", value="en_us")
                    zip_input = gr.File(
                        label="모드팩 ZIP 파일 업로드", file_types=[".zip"]
                    )
                    existing_translation_zip_input = gr.File(
                        label="기존 번역본 ZIP (선택)",
                        file_types=[".zip"],
                        value=None,
                    )
                    custom_dictionary_input = gr.File(
                        label="사전 파일 업로드",
                        file_types=[".json"],
                        value=None,
                    )
                    with gr.Row():
                        build_dict = gr.Checkbox(
                            label="기존 번역에서 사전 자동 구축", value=True
                        )
                        skip_translated = gr.Checkbox(
                            label="이미 번역된 파일 건너뛰기", value=True
                        )
                    resourcepack_name = gr.Textbox(
                        label="리소스팩 이름",
                        value="Auto-Translated-KO",
                    )
                    with gr.Row():
                        gr.Markdown("")
                        translate_config = gr.Checkbox(
                            label="Config 파일 번역", value=True
                        )
                        translate_kubejs = gr.Checkbox(
                            label="KubeJS 파일 번역", value=True
                        )
                        translate_mods = gr.Checkbox(label="Mods 파일 번역", value=True)
                        translate_patchouli_books = gr.Checkbox(
                            label="Patchouli 책 번역 (모드 안에 있는건 이미 자동 번역됨)",
                            value=True,
                        )
                    with gr.Row():
                        max_workers = gr.Number(
                            label="동시 작업자 수", value=5, maximum=30
                        )
                        file_split_number = gr.Number(
                            label="파일 분할 작업자 수", value=1, maximum=5
                        )
                    use_random_order = gr.Checkbox(label="랜덤 순서로 번역", value=True)
                    force_keep_line_break = gr.Checkbox(
                        label="줄바꿈 강제 유지", value=True
                    )
                    with gr.Row():
                        share_results = gr.Checkbox(
                            label="번역 결과 공유 (Discord)", value=True
                        )

            with gr.Column(scale=1, min_width=300):
                translate_btn = gr.Button("번역 시작")
                progress_bar_box = gr.Label(
                    value="Waiting for starting...", label="진행 상황"
                )
                pr = gr.Progress(track_tqdm=True)

                log_output = gr.Textbox(
                    label="진행 상황 로그",
                    lines=15,
                    interactive=False,
                    placeholder="번역 로그가 여기에 표시됩니다...",
                )
                detail_log_output = gr.Textbox(
                    label="상세 로그 (이전 로그도 같이 표시될 수 있음)",
                    lines=40,
                    interactive=False,
                    placeholder="상세 번역 로그가 여기에 표시됩니다...",
                )
                download = gr.DownloadButton(label="번역 결과 다운로드", visible=False)

        def start_translation(
            source_lang,
            zip_file,
            existing_translation_zip,
            custom_dictionary_json,
            build_dict,
            skip_translated,
            resourcepack_name,
            translate_config,
            translate_kubejs,
            translate_mods,
            translate_patchouli_books,
            max_workers,
            file_split_number,
            use_random_order,
            share_results,
            config,
            force_keep_line_break,
            pr=pr,
        ):
            logger_client = Logger(config["log_file_path"])
            logger_client.reset_logs()

            def add_log(message):
                logger_client.write(message)

            add_log("번역 프로세스 시작")
            # 초기 진행률 0%
            # 모델 설정
            provider = config.get("provider")
            model_name = config.get("model_name")
            temperature = config.get("temperature")
            add_log(f"모델 설정: {provider}, {model_name}, 온도={temperature}")
            # ZIP 압축 해제 (Gradio File 객체 지원)
            os.makedirs("./temp/progress", exist_ok=True)
            # UUID 대신 짧은 임의 문자열 사용
            short_id = str(int(time.time() * 1000))[-8:]  # 마지막 8자리 사용
            temp_dir = f"./temp/progress/{short_id}"
            input_dir = os.path.join(temp_dir, "input").replace("\\", "/")
            output_dir = os.path.join(temp_dir, "output").replace("\\", "/")
            os.makedirs(input_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            with zipfile.ZipFile(zip_file.name, "r") as zf:
                zf.extractall(input_dir)
            add_log("ZIP 압축 해제 완료")

            if existing_translation_zip:
                try:
                    with zipfile.ZipFile(existing_translation_zip.name, "r") as zf:
                        for file in zf.namelist():
                            if not file.endswith(".tmp") or not file.endswith(
                                ".converted"
                            ):
                                zf.extract(file, temp_dir)
                    add_log(f"기존 번역본 ZIP 압축 해제 완료: {output_dir}")
                except Exception as e:
                    add_log(f"기존 번역본 ZIP 처리 중 오류 발생: {e}")

            # 모드팩 디렉토리 스캔하여 번역 대상 파일 검색
            files, mods_jars, jar_fingerprints = process_modpack_directory(
                input_dir,
                source_lang,
                translate_config,
                translate_kubejs,
                translate_mods,
                translate_patchouli_books,
            )
            add_log(f"{len(files)}개의 언어 파일 발견")
            # 번역 대상 파일 쌍 생성
            file_pairs = []
            for file_path in files:
                out_path = file_path.replace(input_dir, output_dir, 1)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                file_pairs.append({"input": file_path, "output": out_path})
            total = len(file_pairs)
            # JSON 번역 실행 (파일 레벨 병렬) 및 진행률 전송
            add_log(f"총 {total}개의 파일 병렬 번역 시작")
            # 진행률 초기화
            pr(0, total=total, desc="준비중..")

            # 모든 파일 번역 실행 (프로그래스 콜백 전달)
            async def progress_callback(progress):
                pr(
                    progress[0] / progress[1],
                    desc=f"번역 중.. ({progress[0]}/{progress[1]})",
                )

            results, dict_init = asyncio.run(
                run_json_translation(
                    file_pairs,
                    source_lang,
                    config,
                    build_dict,
                    skip_translated,
                    max_workers,
                    file_split_number,
                    use_random_order,
                    custom_dictionary_path=custom_dictionary_json.name
                    if custom_dictionary_json
                    else None,
                    progress_callback=progress_callback,
                    logger_client=logger_client,
                    force_keep_line_break=force_keep_line_break,
                )
            )
            # 진행률 완료
            pr(1, desc="번역 완료")

            restore_zip_files(output_dir)

            add_log("모든 파일 번역 완료")
            # 리소스팩 카테고리별 생성 (Async Queue)
            add_log("리소스팩 생성 중...")
            # categories_info = {
            #     "mods": {"suffix": "_MOD_TRANSLATION"},
            #     "config": {"suffix": "_CONFIG_TRANSLATION"},
            #     "kubejs": {"suffix": "_KUBEJS_TRANSLATION"},
            #     "patchouli_books": {"suffix": "_PATCHOULI_BOOKS_TRANSLATION"},
            # }
            # created_packs = asyncio.run(
            #     package_categories(
            #         output_dir,
            #         categories_info,
            #         translate_config,
            #         translate_kubejs,
            #         translate_mods,
            #         resourcepack_name,
            #     )
            # )
            # add_log(f"{len(created_packs)}개의 리소스팩 생성 완료")
            # # 최종 ZIP 생성
            folders_to_add = [
                os.path.join(output_dir, "kubejs"),
                os.path.join(output_dir, "config"),
                os.path.join(output_dir, "patchouli_books"),
            ]
            mods_resource_pack = create_resourcepack(
                output_dir,
                [
                    os.path.join(output_dir, "mods", "extracted"),
                ],
                resourcepack_name + "_RESOURCEPACK",
            )
            os.makedirs("./temp/translated_resourcepacks", exist_ok=True)
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".zip",
                mode="wb",
                dir="./temp/translated_resourcepacks",
            ) as temp_zip_file:
                with zipfile.ZipFile(
                    temp_zip_file.name, "w", zipfile.ZIP_DEFLATED
                ) as zf:
                    zf.write(
                        mods_resource_pack, arcname=os.path.basename(mods_resource_pack)
                    )
                    for folder in folders_to_add:
                        folder = folder.replace("\\", "/")
                        if os.path.exists(folder) and any(os.scandir(folder)):
                            for root, _, files in os.walk(folder):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    if (
                                        not file.endswith(".tmp")
                                        and not file.endswith(".converted")
                                        and ".zip_extracted" not in file_path
                                    ):
                                        arcname = os.path.join(
                                            os.path.basename(folder),
                                            os.path.relpath(file_path, folder),
                                        )
                                        zf.write(file_path, arcname=arcname)
                    zf.writestr(
                        "한글패치 적용 가이드.md",
                        HOW_TO_APPLY_PATCH.format(
                            resourcepack_name=resourcepack_name,
                            temperature=temperature,
                            model=model_name,
                            provider=provider,
                            worker_num=max_workers,
                            file_split=file_split_number,
                            version=minecraft_modpack_auto_translator.__version__,
                        ),
                    )
                    try:
                        dict_json = json.dumps(dict_init, ensure_ascii=False, indent=4)
                        zf.writestr("translation_dictionary.json", dict_json)
                        add_log("번역 사전을 ZIP 파일에 저장 완료")
                    except Exception as e:
                        add_log(f"번역 사전 저장 중 오류 발생: {e}")

                final_zip_path = temp_zip_file.name  # 파일 경로 저장

            add_log(f"최종 ZIP 생성 완료: {final_zip_path}")

            # jar_fingerprints를 Discord로 공유
            if share_results:
                try:
                    fingerprint_path = os.path.join(temp_dir, "fingerprint.json")
                    error_path = "./temp/error_list.json"
                    with open(fingerprint_path, "w", encoding="utf-8") as f:
                        json.dump(jar_fingerprints, f, ensure_ascii=False, indent=4)
                    share_zip_path = os.path.join(temp_dir, "shared_result.zip")
                    with zipfile.ZipFile(
                        share_zip_path, "w", zipfile.ZIP_DEFLATED
                    ) as share_zf:
                        if os.path.exists(fingerprint_path):
                            share_zf.write(fingerprint_path, arcname="fingerprint.json")
                        if os.path.exists(error_path):
                            share_zf.write(error_path, arcname="error_list.json")
                        for jar_name in jar_fingerprints.keys():
                            extract_path = os.path.join(
                                output_dir, "mods", "extracted", jar_name
                            )
                            for root, _, share_files in os.walk(extract_path):
                                for sf in share_files:
                                    if not sf.endswith(".tmp"):
                                        src_file = os.path.join(root, sf)
                                        arc = (
                                            os.path.join(
                                                jar_name,
                                                os.path.relpath(src_file, extract_path),
                                            )
                                            .replace(
                                                source_lang.split("_")[0]
                                                + "_"
                                                + source_lang.split("_")[1].upper(),
                                                "ko_KR",
                                            )
                                            .replace(source_lang, "ko_kr")
                                        )
                                        share_zf.write(src_file, arcname=arc)

                    # 서버 URL 정의 (환경 변수나 설정 파일에서 가져오는 것이 더 좋음)
                    SERVER_URL = os.getenv(
                        "UPLOAD_SERVER_URL",
                        "http://mc-share.2odk.com",
                    )  # 환경 변수 우선 사용

                    zip_name = os.path.basename(zip_file.name)

                    # 서버로 전송할 데이터 구성
                    form_data = {
                        "provider": provider,
                        "model_name": model_name,
                        "temperature": str(temperature),  # 숫자는 문자열로 변환
                        "file_split_number": str(
                            file_split_number
                        ),  # 숫자는 문자열로 변환
                        "zip_name": zip_name,
                        "resourcepack_name": resourcepack_name,
                    }

                    try:
                        url = f"{SERVER_URL}/upload_to_discord/"
                        add_log(f"Fingerprinnt를 서버 ({url})로 전송 중...")
                        # 파일을 열어서 전송
                        with open(share_zip_path, "rb") as f:
                            files_data = {
                                "file": (
                                    f"{zip_name}.zip",
                                    f,
                                    "application/zip",
                                )  # 파일 이름 고정 또는 share_zip_path 기반으로 동적 생성 가능
                            }
                            response = requests.post(
                                url,
                                data=form_data,
                                files=files_data,
                                timeout=300,
                            )  # 타임아웃 추가

                        # 서버 응답 확인
                        if response.status_code == 200:
                            response_json = response.json()
                            log_message = f"서버 전송 완료: {response_json.get('message', '성공')}"
                            if response_json.get("url"):
                                log_message += f" (URL: {response_json['url']})"
                            add_log(log_message)
                        else:
                            add_log(
                                f"서버 전송 실패: 상태 코드 {response.status_code}, 응답: {response.text}"
                            )

                        url = f"{SERVER_URL}/upload_modpack/"
                        add_log(f"Modpack 번역 결과를 서버 ({url})로 전송 중...")
                        with open(final_zip_path, "rb") as f:
                            files_data = {
                                "file": (
                                    f"{zip_name}.zip",
                                    f,
                                    "application/zip",
                                )  # 파일 이름 고정 또는 share_zip_path 기반으로 동적 생성 가능
                            }
                            response = requests.post(
                                url,
                                data=form_data,
                                files=files_data,
                                timeout=300,
                            )  # 타임아웃 추가

                        # 서버 응답 확인
                        if response.status_code == 200:
                            response_json = response.json()
                            log_message = f"서버 전송 완료: {response_json.get('message', '성공')}"
                            if response_json.get("url"):
                                log_message += f" (URL: {response_json['url']})"
                            add_log(log_message)
                        else:
                            add_log(
                                f"서버 전송 실패: 상태 코드 {response.status_code}, 응답: {response.text}"
                            )

                    except requests.exceptions.RequestException as e:
                        add_log(f"서버 전송 오류: {e}")
                    except Exception as e:
                        add_log(f"결과 전송 중 예외 발생: {e}")
                    finally:
                        # 임시 파일 삭제 (필요한 경우 유지)
                        # os.remove(share_zip_path)
                        pass  # Gradio에서 처리한다면 여기서 삭제 불필요

                except Exception as e:
                    print(f"공유 중 오류: {e}")
            return "Waiting for starting...", gr.update(
                value=final_zip_path, visible=True
            )

        translate_btn.click(
            start_translation,
            inputs=[
                source_lang,
                zip_input,
                existing_translation_zip_input,
                custom_dictionary_input,
                build_dict,
                skip_translated,
                resourcepack_name,
                translate_config,
                translate_kubejs,
                translate_mods,
                translate_patchouli_books,
                max_workers,
                file_split_number,
                use_random_order,
                share_results,
                config_state,
                force_keep_line_break,
            ],
            outputs=[progress_bar_box, download],
        )

        def update_log(config):
            log_file_path = config.get("log_file_path")
            if log_file_path:
                logger_client = Logger(log_file_path)
                return gr.update(value=logger_client.read_logs())

        def detail_update_log():
            logger_client = Logger("./translation.log")
            return gr.update(value=logger_client.read_logs())

        gr.Timer(3).tick(fn=update_log, inputs=[config_state], outputs=log_output)
        gr.Timer(3).tick(fn=detail_update_log, outputs=detail_log_output)
    return tab
