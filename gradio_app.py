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

    print("Gradio 서버 시작")
    print(f"서버 이름: {os.getenv('SERVER_NAME', '0.0.0.0')}")
    print(f"서버 포트: {os.getenv('SERVER_PORT', 7860)}")
    print(f"공유 여부: {os.getenv('SHARE', False)}")
    print(f"API 표시 여부: {os.getenv('SHOW_API', False)}")
    print(f"최대 파일 크기: {os.getenv('MAX_FILE_SIZE_GB', 100)}GB")

    print("=" * 20)
    print(
        f"\n웹 브라우저에서 http://localhost:{os.getenv('SERVER_PORT', 7860)}/gradio-demo 로 접속하세요.\n"
    )
    print("=" * 20)

    demo.launch(
        server_name=os.getenv("SERVER_NAME", "0.0.0.0"),
        server_port=int(os.getenv("SERVER_PORT", 7860)),
        share=os.getenv("SHARE", False),
        show_api=os.getenv("SHOW_API", False),
        max_file_size=1024 * 1024 * 1024 * int(os.getenv("MAX_FILE_SIZE_GB", 100)),
        root_path="/gradio-demo",
        debug=True,
    )


if __name__ == "__main__":
    main()
