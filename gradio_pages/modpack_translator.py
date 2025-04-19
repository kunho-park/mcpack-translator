import asyncio
import datetime
import io
import json
import os
import tempfile
import zipfile

import gradio as gr
from apscheduler.schedulers.background import BackgroundScheduler
from catboxpy.catbox import CatboxClient
from discord_webhook import DiscordWebhook

from gradio_modules.dictionary_builder import process_modpack_directory
from gradio_modules.logger import Logger
from gradio_modules.packager import package_categories
from gradio_modules.translator import run_json_translation

# 스케줄러 초기화 및 시작
scheduler = BackgroundScheduler()
scheduler.start()


# 임시 파일 삭제 함수
def delete_file_later(file_path):
    try:
        os.remove(file_path)
        print(f"임시 파일 삭제 완료: {file_path}")
    except OSError as e:
        print(f"임시 파일 삭제 오류 ({file_path}): {e}")


catbox_client = CatboxClient(userhash=os.getenv("CATBOX_USERHASH"))


def create_modpack_translator_ui(config_state):
    with gr.Blocks() as tab:
        gr.Markdown("## 🌐 원클릭 모드팩 번역기")

        with gr.Accordion("번역 옵션", open=True):
            source_lang = gr.Textbox(label="원본 언어 코드", value="en_us")
            zip_input = gr.File(label="모드팩 ZIP 파일 업로드", file_types=[".zip"])
            build_dict = gr.Checkbox(label="기존 번역에서 사전 자동 구축", value=True)
            skip_translated = gr.Checkbox(label="이미 번역된 파일 건너뛰기", value=True)
            resourcepack_name = gr.Textbox(
                label="리소스팩 이름", value="Auto-Translated-KO"
            )
            translate_config = gr.Checkbox(label="Config 파일 번역", value=True)
            translate_kubejs = gr.Checkbox(label="KubeJS 파일 번역", value=True)
            translate_mods = gr.Checkbox(label="Mods 파일 번역", value=True)
            max_workers = gr.Number(label="동시 작업자 수", value=5, maximum=10)
            file_split_number = gr.Number(
                label="파일 분할 작업자 수", value=1, maximum=5
            )
            use_random_order = gr.Checkbox(label="랜덤 순서로 번역", value=False)

            share_results = gr.Checkbox(label="번역 결과 공유 (Discord)", value=True)

        translate_btn = gr.Button("번역 시작")

        progress_bar_box = gr.Label(value="Waiting for starting...")
        pr = gr.Progress(track_tqdm=True)

        log_output = gr.Textbox(
            label="상세 로그",
            lines=10,
            interactive=False,
            placeholder="번역 로그가 여기에 표시됩니다...",
        )
        download = gr.DownloadButton(label="번역 결과 다운로드", visible=False)

        def start_translation(
            source_lang,
            zip_file,
            build_dict,
            skip_translated,
            resourcepack_name,
            translate_config,
            translate_kubejs,
            translate_mods,
            max_workers,
            file_split_number,
            use_random_order,
            share_results,
            config,
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
            temp_dir = tempfile.TemporaryDirectory()
            input_dir = os.path.join(temp_dir.name, "input")
            output_dir = os.path.join(temp_dir.name, "output")
            os.makedirs(input_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            with zipfile.ZipFile(zip_file.name, "r") as zf:
                zf.extractall(input_dir)
            add_log("ZIP 압축 해제 완료")
            # 모드팩 디렉토리 스캔하여 번역 대상 파일 검색
            files, mods_jars, jar_fingerprints = process_modpack_directory(
                input_dir,
                source_lang,
                translate_config,
                translate_kubejs,
                translate_mods,
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
                pr(progress[0] / progress[1], desc="번역 중..")

            asyncio.run(
                run_json_translation(
                    file_pairs,
                    source_lang,
                    config,
                    build_dict,
                    skip_translated,
                    max_workers,
                    file_split_number,
                    use_random_order,
                    progress_callback=progress_callback,
                    logger_client=logger_client,
                )
            )
            # 진행률 완료
            pr(1, desc="번역 완료")
            add_log("모든 파일 번역 완료")
            # 리소스팩 카테고리별 생성 (Async Queue)
            add_log("리소스팩 생성 중...")
            categories_info = {
                "mods": {"suffix": "_MOD_TRANSLATION"},
                "config": {"suffix": "_CONFIG_TRANSLATION"},
                "kubejs": {"suffix": "_KUBEJS_TRANSLATION"},
            }
            created_packs = asyncio.run(
                package_categories(
                    output_dir,
                    categories_info,
                    translate_config,
                    translate_kubejs,
                    translate_mods,
                    resourcepack_name,
                )
            )
            add_log(f"{len(created_packs)}개의 리소스팩 생성 완료")
            # 최종 ZIP 생성
            final_buf = io.BytesIO()
            with zipfile.ZipFile(final_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for pack in created_packs:
                    zf.write(pack["path"], arcname=os.path.basename(pack["path"]))
            final_buf.seek(0)

            # 임시 파일로 최종 ZIP 저장 (NamedTemporaryFile 사용)
            os.makedirs("./temp/translated_resourcepacks", exist_ok=True)
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".zip",
                mode="wb",
                dir="./temp/translated_resourcepacks",
            ) as temp_zip_file:
                temp_zip_file.write(final_buf.getvalue())
                final_zip_path = temp_zip_file.name  # 파일 경로 저장

            add_log(f"최종 ZIP 생성 완료: {final_zip_path}")

            # 30분 후 임시 파일 삭제 예약
            run_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
            scheduler.add_job(
                delete_file_later,
                trigger="date",
                run_date=run_time,
                args=[final_zip_path],
            )
            print(f"임시 파일 삭제 예약됨 ({final_zip_path}) at {run_time}")

            # jar_fingerprints를 Discord로 공유
            if share_results:
                try:
                    fingerprint_path = os.path.join(temp_dir.name, "fingerprint.json")
                    with open(fingerprint_path, "w", encoding="utf-8") as f:
                        json.dump(jar_fingerprints, f, ensure_ascii=False, indent=4)
                    share_zip_path = os.path.join(temp_dir.name, "shared_result.zip")
                    with zipfile.ZipFile(
                        share_zip_path, "w", zipfile.ZIP_DEFLATED
                    ) as share_zf:
                        share_zf.write(fingerprint_path, arcname="fingerprint.json")
                        for jar_name in jar_fingerprints.keys():
                            extract_path = os.path.join(
                                input_dir, "extracted", jar_name
                            )
                            for root, _, share_files in os.walk(extract_path):
                                for sf in share_files:
                                    if not sf.endswith(".tmp"):
                                        src_file = os.path.join(root, sf)
                                        arc = os.path.join(
                                            jar_name,
                                            os.path.relpath(src_file, extract_path),
                                        )
                                        share_zf.write(src_file, arcname=arc)

                    if os.getenv("DISCORD_WEBHOOK_URL"):
                        file_size = os.path.getsize(share_zip_path) / (
                            1000 * 1000
                        )  # MB 단위로 변환

                        if file_size <= 25:
                            # 25MB 이하 - 디스코드로 직접 전송
                            with open(share_zip_path, "rb") as f:
                                webhook = DiscordWebhook(
                                    url=os.getenv("DISCORD_WEBHOOK_URL"),
                                    content=f"번역 결과 파일 (직접 업로드)\n\n모델 정보:\n- Provider: {provider}\n- Model: {model_name}\n- Temperature: {temperature}\n- 병렬 요청 분할: {file_split_number}\n",
                                    thread_name=f"모드팩 번역 결과 ({resourcepack_name})",
                                )
                                webhook.add_file(
                                    file=f.read(), filename="translation_results.zip"
                                )
                                webhook.execute()
                        else:
                            # 25MB 초과 - Catbox 사용
                            share_url = catbox_client.upload(share_zip_path)
                            webhook = DiscordWebhook(
                                url=os.getenv("DISCORD_WEBHOOK_URL"),
                                content=f"{share_url}\n\n모델 정보:\n- Provider: {provider}\n- Model: {model_name}\n- Temperature: {temperature}\n- 병렬 요청 분할: {file_split_number}\n",
                                thread_name=f"모드팩 번역 결과 ({resourcepack_name})",
                            )
                            webhook.execute()

                        add_log("공유 링크 전송됨")
                    else:
                        add_log(
                            "디스코드로의 공유를 원하신다면 https://mc-pack-translator.2odk.com 에서 번역을 해주세요."
                        )
                        gr.Info(
                            "디스코드로의 공유를 원하신다면 https://mc-pack-translator.2odk.com 에서 번역을 해주세요."
                        )
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
                build_dict,
                skip_translated,
                resourcepack_name,
                translate_config,
                translate_kubejs,
                translate_mods,
                max_workers,
                file_split_number,
                use_random_order,
                share_results,
                config_state,
            ],
            outputs=[progress_bar_box, download],
        )

        def update_log(config):
            logger_client = Logger(config["log_file_path"])
            return gr.update(value=logger_client.read_logs())

        gr.Timer(3).tick(fn=update_log, inputs=[config_state], outputs=log_output)
    return tab
