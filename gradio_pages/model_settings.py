import datetime
import json
import os
import tempfile

import gradio as gr
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.start()


# 임시 파일 삭제 함수
def delete_file_later(file_path):
    try:
        os.remove(file_path)
        print(f"임시 파일 삭제 완료: {file_path}")
    except OSError as e:
        print(f"임시 파일 삭제 오류 ({file_path}): {e}")


def create_model_settings_ui(config_state):
    with gr.Column():
        gr.Markdown("## ⚙️ 모델 설정")
        provider = gr.Dropdown(
            choices=["OpenAI", "Google", "Grok", "Ollama", "Anthropic", "G4F"],
            label="모델 제공자",
            value="G4F",
        )
        api_keys = gr.Textbox(
            label="API 키들 (줄바꿈으로 구분)",
            placeholder="각 키를 줄바꿈으로 입력하세요",
            lines=4,
            value="sk-proj-1234567890",
        )
        api_base = gr.Textbox(label="API Base URL", placeholder="(선택 사항)")
        model_name = gr.Textbox(
            label="모델 이름",
            placeholder="모델 이름을 입력하세요",
            value="gpt-4o",
        )
        temperature = gr.Slider(
            label="온도 (Temperature)", minimum=0.0, maximum=2.0, step=0.01, value=0
        )
        with gr.Row():
            gr.Markdown("## Gemini 2.5 Flash 전용 옵션")
            use_thinking_budget = gr.Checkbox(
                label="생각 비용 사용 (Thinking Budget)", value=False
            )
            thinking_budget = gr.Slider(
                label="생각 비용 (Thinking Budget)",
                minimum=0,
                maximum=1024,
                step=1,
                value=0,
            )
        with gr.Row():
            use_rate_limiter = gr.Checkbox(label="속도 제한 사용 (RPM)", value=False)
            rpm = gr.Number(
                label="분당 최대 요청 수 (RPM)",
                value=60,
                minimum=1,
                step=1,
                interactive=True,
            )
        with gr.Row():
            use_request_delay = gr.Checkbox(label="요청 간 지연 사용", value=False)
            request_delay = gr.Number(
                label="요청 간 지연 시간 (초)",
                value=1.0,
                minimum=0.0,
                step=0.1,
                interactive=True,
            )
        save_btn = gr.Button("설정 저장")

        def save_settings(
            config,
            provider,
            api_keys,
            api_base,
            model_name,
            temperature,
            use_thinking_budget,
            thinking_budget,
            use_rate_limiter,
            rpm,
            use_request_delay,
            request_delay,
        ):
            # Parse multiple API keys input into a list
            keys = [k.strip() for k in api_keys.splitlines() if k.strip()]
            config.update(
                {
                    "provider": provider,
                    "api_keys": keys,
                    "api_base": api_base,
                    "model_name": model_name,
                    "temperature": temperature,
                    "use_thinking_budget": use_thinking_budget,
                    "thinking_budget": thinking_budget,
                    "use_rate_limiter": use_rate_limiter,
                    "rpm": int(rpm),
                    "use_request_delay": use_request_delay,
                    "request_delay": float(request_delay),
                }
            )
            gr.Success("설정이 저장되었습니다.")
            return config

        save_btn.click(
            save_settings,
            inputs=[
                config_state,
                provider,
                api_keys,
                api_base,
                model_name,
                temperature,
                use_thinking_budget,
                thinking_budget,
                use_rate_limiter,
                rpm,
                use_request_delay,
                request_delay,
            ],
            outputs=config_state,
        )
        # 설정 내보내기 버튼
        export_btn = gr.DownloadButton(
            label="설정 내보내기",
        )

        def export_settings(config):
            config_json = json.dumps(config, ensure_ascii=False, indent=4)

            os.makedirs("./temp/config", exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                delete=False,
                prefix="settings_export_",
                dir="./temp/config",
            ) as tmp:
                tmp.write(config_json)
                tmp_path = tmp.name
            run_time = datetime.datetime.now() + datetime.timedelta(minutes=1)
            scheduler.add_job(
                delete_file_later,
                trigger="date",
                run_date=run_time,
                args=[tmp_path],
            )
            return tmp_path

        export_btn.click(export_settings, inputs=[config_state], outputs=export_btn)

        # 설정 가져오기 버튼 & 파일 업로드
        import_file = gr.File(label="설정 파일 업로드", file_types=[".json"])
        load_btn = gr.Button("설정 불러오기")

        def import_settings(file):
            try:
                with open(file.name, "rb") as f:
                    raw = f.read().decode("utf-8")
                    data = json.loads(raw)
            except Exception:
                gr.Error("설정을 불러오는데 실패했습니다.")
                return (
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                )
            # Multi API 키 지원: api_keys 또는 기존 api_key 필드를 적절히 변환
            api_keys_str = ""
            if "api_keys" in data:
                api_keys_str = "\n".join(data["api_keys"])
            elif "api_key" in data:
                api_keys_str = data["api_key"]
            # config_state 및 UI 컴포넌트 업데이트
            data["log_file_path"] = tempfile.NamedTemporaryFile(
                delete=False,
                prefix="log_",
                dir="./temp/logs",
                suffix=".log",
            ).name
            return (
                data,
                data.get("provider"),
                api_keys_str,
                data.get("api_base"),
                data.get("model_name"),
                data.get("temperature"),
                data.get("use_thinking_budget", False),
                data.get("thinking_budget", 0),
                data.get("use_rate_limiter", False),
                data.get("rpm", 60),
                data.get("use_request_delay", False),
                data.get("request_delay", 1.0),
            )

        load_btn.click(
            import_settings,
            inputs=[import_file],
            outputs=[
                config_state,
                provider,
                api_keys,
                api_base,
                model_name,
                temperature,
                use_thinking_budget,
                thinking_budget,
                use_rate_limiter,
                rpm,
                use_request_delay,
                request_delay,
            ],
        )
