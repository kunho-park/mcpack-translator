import gradio as gr


def create_home_ui():
    with gr.Blocks() as home_tab:
        gr.Markdown("# 🏠 홈")
        gr.Markdown("마인크래프트 모드팩 자동 번역기에 오신 것을 환영합니다!")
        gr.Markdown("왼쪽 탭 메뉴에서 원하는 번역 기능을 선택하세요.")
    return home_tab
