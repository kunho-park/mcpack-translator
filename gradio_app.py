import os
from tempfile import NamedTemporaryFile

import gradio as gr
from dotenv import load_dotenv

from gradio_pages.file_translator import create_file_translator_ui
from gradio_pages.home import create_home_ui
from gradio_pages.model_settings import create_model_settings_ui
from gradio_pages.modpack_translator import create_modpack_translator_ui

load_dotenv()


def main():
    with gr.Blocks() as demo:
        # 상태 저장용 변수
        os.makedirs("./temp/logs", exist_ok=True)
        config_state = gr.State(
            {
                "provider": "G4F",
                "api_key": "",
                "api_base": "",
                "model_name": "gpt-4o",
                "temperature": 0,
                "log_file_path": NamedTemporaryFile(
                    delete=False, prefix="log_", dir="./temp/logs"
                ).name,
            }
        )

        with gr.Tabs():
            with gr.TabItem("🏠 홈"):
                create_home_ui()
            with gr.TabItem("🌐 원클릭 모드팩 번역기"):
                create_modpack_translator_ui(config_state)
            with gr.TabItem("📄 단일 파일 번역기"):
                create_file_translator_ui(config_state)
            with gr.TabItem("⚙️ 모델 설정"):
                create_model_settings_ui(config_state)

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_api=False,
        max_file_size=1024 * 1024 * 1024 * int(os.getenv("MAX_FILE_SIZE_GB")),
    )


if __name__ == "__main__":
    main()
