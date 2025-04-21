import gradio as gr


def create_home_ui():
    with gr.Blocks() as home_tab:
        gr.Markdown("# 🏠 홈")
        gr.Markdown("마인크래프트 모드팩 자동 번역기에 오신 것을 환영합니다!")
        gr.Markdown("왼쪽 탭 메뉴에서 원하는 번역 기능을 선택하세요.")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📌 주요 기능")
                gr.Markdown("- 🌐 원클릭 모드팩 번역")
                gr.Markdown("- 📄 단일 파일 번역")
                gr.Markdown("- ⚙️ 모델 설정 관리")

            with gr.Column():
                gr.Markdown("### 🔗 유용한 링크")
                gr.Markdown(
                    "### 🤖 [Discord 커뮤니티 참가하기](https://discord.com/invite/UfAEF4CJ45)"
                )
                gr.Markdown(
                    "### 📂 [GitHub 저장소 방문하기](https://github.com/kunho-park/mcpack-translator)"
                )
                gr.Markdown(
                    "### 📖 [사용 설명서 보기](https://kunho-park.notion.site/AI-mcpack-translator-1dc8edfca9988073a109f2b746f1aa8d)"
                )
    return home_tab
