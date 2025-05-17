import logging
import os
import shutil
import time
import zipfile
from datetime import datetime

import gradio as gr
from apscheduler.schedulers.background import BackgroundScheduler

from gradio_modules.dictionary_builder import (
    extact_all_zip_files,
    process_modpack_directory,
    restore_zip_files,
)
from minecraft_modpack_auto_translator.parsers import BaseParser

logger = logging.getLogger(__name__)

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


def create_update_modpack_ui():
    with gr.Blocks() as tab:
        gr.Markdown("## 🛠️ 번역 업데이트 프로그램")
        with gr.Accordion("📖 사용 설명서 (클릭하여 펼치기)", open=False):
            gr.Markdown("""
            ### 🌟 번역 업데이트 프로그램 사용 가이드
            
            구버전을 번역하였는데 신버전에도 적용하고 싶을때 사용하는 기능입니다.
            
            **📌 기본 사용법:**
            1. 모드팩 ZIP 파일을 업로드하세요
            2. 구버전에서 번역한 모드팩 설정, 리소스팩을 업로드하세요
            3. 업데이트 옵션을 설정한 후 '업데이트 시작' 버튼을 클릭하세요
            4. 업데이트가 완료되면 결과 ZIP 파일을 다운로드 받으세요
            """)
        with gr.Row():
            with gr.Column(scale=1, min_width=300):
                with gr.Accordion("번역 옵션", open=True):
                    source_lang = gr.Textbox(label="원본 언어 코드", value="en_us")

                    resourcepack_zip_input = gr.File(
                        label="기존 번역본 리소스팩",
                        file_types=[".zip"],
                        value=None,
                    )
                    modpack_zip_input_old = gr.File(
                        label="기존 번역본 모드팩 설정 ZIP (config, kubejs 폴더 포함)",
                        file_types=[".zip"],
                        value=None,
                    )
                    modpack_zip_input = gr.File(
                        label="신 버전 모드팩 ZIP",
                        file_types=[".zip"],
                        value=None,
                    )

            with gr.Column(scale=1, min_width=300):
                update_btn = gr.Button("업데이트 시작")
                gr.Markdown("### 📥 결과 다운로드")
                output_resourcepack_zip = gr.File(
                    label="업데이트된 리소스팩 ZIP", file_types=[".zip"]
                )
                output_modpack_zip = gr.File(
                    label="업데이트된 모드팩 설정 ZIP", file_types=[".zip"]
                )

        def start_update(modpack_zip, modpack_zip_old, resourcepack_zip, source_lang):
            os.makedirs("./temp/update_progress", exist_ok=True)
            short_id = str(int(time.time() * 1000))[-8:]  # 마지막 8자리 사용
            temp_dir = f"./temp/update_progress/{short_id}"
            modpack_dir = os.path.join(temp_dir, "modpack").replace("\\\\", "/")
            old_modpack_dir = os.path.join(temp_dir, "old_modpack").replace("\\\\", "/")
            resourcepack_dir = os.path.join(temp_dir, "resourcepack").replace(
                "\\\\", "/"
            )

            output_zip_dir = os.path.join(temp_dir, "output_zips").replace("\\\\", "/")
            os.makedirs(output_zip_dir, exist_ok=True)

            os.makedirs(modpack_dir, exist_ok=True)
            os.makedirs(old_modpack_dir, exist_ok=True)
            os.makedirs(resourcepack_dir, exist_ok=True)

            with zipfile.ZipFile(modpack_zip_old.name, "r") as zf:
                zf.extractall(old_modpack_dir)
            with zipfile.ZipFile(modpack_zip.name, "r") as zf:
                zf.extractall(modpack_dir)
            with zipfile.ZipFile(resourcepack_zip.name, "r") as zf:
                zf.extractall(resourcepack_dir)

            files, mods_jars, jar_fingerprints = process_modpack_directory(
                modpack_dir,
                source_lang,
                True,
                True,
                True,
                True,
            )
            extact_all_zip_files(old_modpack_dir)

            for file in files:
                file = file.replace(source_lang, "ko_kr")
                parser = BaseParser.get_parser_by_extension(os.path.splitext(file)[1])
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        new_data = parser.load(f.read())
                except Exception:
                    logger.error(f"파일을 읽을 수 없습니다: {file}")
                    continue

                relative_path = os.path.relpath(file, modpack_dir)

                if "assets" in relative_path:
                    path_in_resourcepack = relative_path[relative_path.find("assets") :]
                    resourcepack_file_path = os.path.join(
                        resourcepack_dir, path_in_resourcepack
                    ).replace("\\", "/")
                else:
                    resourcepack_file_path = os.path.join(
                        resourcepack_dir, relative_path
                    ).replace("\\", "/")

                old_modpack_file_path = os.path.join(
                    old_modpack_dir, relative_path
                ).replace("\\", "/")

                results = {}
                try:
                    old_data_source_path = None
                    if os.path.exists(resourcepack_file_path):
                        with open(resourcepack_file_path, "r", encoding="utf-8") as f:
                            old_data = parser.load(f.read())
                        old_data_source_path = resourcepack_file_path
                    elif os.path.exists(old_modpack_file_path):
                        with open(old_modpack_file_path, "r", encoding="utf-8") as f:
                            old_data = parser.load(f.read())
                        old_data_source_path = old_modpack_file_path
                    else:
                        old_data = {}

                    for k, v in new_data.items():
                        if k in old_data and old_data[k] != v:
                            results[k] = old_data[k]
                        else:
                            results[k] = v

                    if old_data_source_path:
                        parser.save(results, old_data_source_path)

                except FileNotFoundError:
                    logger.error(
                        f"파일을 찾을 수 없습니다: {resourcepack_file_path} 또는 {old_modpack_file_path}"
                    )
                    pass
                except Exception as e:
                    print(f"오류 발생 ({file}): {e}")
                    pass

            updated_resourcepack_zip_path = os.path.join(
                output_zip_dir, f"updated_resourcepack_{short_id}.zip"
            ).replace("\\", "/")
            updated_modpack_zip_path = os.path.join(
                output_zip_dir, f"updated_modpack_settings_{short_id}.zip"
            ).replace("\\", "/")

            restore_zip_files(old_modpack_dir, source_lang)

            with zipfile.ZipFile(
                updated_resourcepack_zip_path, "w", zipfile.ZIP_DEFLATED
            ) as zf:
                for root, _, files_in_dir in os.walk(resourcepack_dir):
                    for file_in_dir in files_in_dir:
                        file_path = os.path.join(root, file_in_dir)
                        arcname = os.path.relpath(file_path, resourcepack_dir)
                        zf.write(file_path, arcname)

            with zipfile.ZipFile(
                updated_modpack_zip_path, "w", zipfile.ZIP_DEFLATED
            ) as zf:
                for root, _, files_in_dir in os.walk(old_modpack_dir):
                    included_folders = ["config", "kubejs", "scripts"]

                    should_include = False
                    if root == old_modpack_dir:
                        should_include = True

                    if not should_include:
                        for included_folder in included_folders:
                            if os.path.relpath(root, old_modpack_dir).startswith(
                                included_folder
                            ):
                                should_include = True
                                break

                    if should_include:
                        for file_in_dir in files_in_dir:
                            file_path = os.path.join(root, file_in_dir)
                            arcname = os.path.relpath(file_path, old_modpack_dir)
                            zf.write(file_path, arcname)

            scheduler.add_job(
                delete_file_later,
                "date",
                run_date=datetime.fromtimestamp(time.time() + 3600),
                args=[updated_resourcepack_zip_path],
                misfire_grace_time=600,
            )
            scheduler.add_job(
                delete_file_later,
                "date",
                run_date=datetime.fromtimestamp(time.time() + 3600),
                args=[updated_modpack_zip_path],
                misfire_grace_time=600,
            )
            scheduler.add_job(
                shutil.rmtree,
                "date",
                run_date=datetime.fromtimestamp(time.time() + 3600),
                args=[modpack_dir],
                misfire_grace_time=600,
                kwargs={"ignore_errors": True},
            )
            scheduler.add_job(
                shutil.rmtree,
                "date",
                run_date=datetime.fromtimestamp(time.time() + 3600),
                args=[old_modpack_dir],
                misfire_grace_time=600,
                kwargs={"ignore_errors": True},
            )
            scheduler.add_job(
                shutil.rmtree,
                "date",
                run_date=datetime.fromtimestamp(time.time() + 3600),
                args=[resourcepack_dir],
                misfire_grace_time=600,
                kwargs={"ignore_errors": True},
            )

            return updated_resourcepack_zip_path, updated_modpack_zip_path

        update_btn.click(
            start_update,
            inputs=[
                modpack_zip_input,
                modpack_zip_input_old,
                resourcepack_zip_input,
                source_lang,
            ],
            outputs=[output_resourcepack_zip, output_modpack_zip],
        )
    return tab
