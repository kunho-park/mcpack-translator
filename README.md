# 🚀 마인크래프트 모드팩 자동 번역기 (v2.0.0)

📖 **자세한 사용 설명서**: [Notion 문서 바로가기](https://kunho-park.notion.site/AI-mcpack-translator-1dc8edfca9988073a109f2b746f1aa8d)

마인크래프트 모드팩을 영어에서 한국어로 자동 번역하는 도구입니다. 마인크래프트 공식 번역 데이터를 활용한 RAG(Retrieval-Augmented Generation)를 통해 고유명사와 포맷 코드를 보존하면서 자연스러운 번역을 제공합니다.

## 📌 주요 기능

- 마인크래프트 모드팩 JSON, LANG, SNBT 파일 번역
- 플레이스홀더(%s, %d 등) 보존
- 포맷 코드(§) 보존
- 대형 언어 모델(LLM)을 활용한 자연스러운 번역
- 고유명사 및 게임 용어 정확한 번역
- 웹 인터페이스 제공

## ⚙️ 기본 요구 사항
- [uv](https://github.com/astral-sh/uv)
- OpenAI API 키, Anthropic API 키, Google AI API 키 중 하나 이상 혹은 Ollama

## 🖥️ 윈도우 자동 설치

### 설치 전 필수 프로그램
1. **Git**: [Git 다운로드 페이지](https://git-scm.com/downloads/win)
2. **uv**: [uv 설치 가이드](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_2)

### 설치 절차
1. [릴리스 페이지](https://github.com/kunho-park/mcpack-translator/releases)에서 최신 버전 다운로드
2. 압축 해제 후 `update.bat` 실행 (최초 1회)
3. `run.bat` 실행으로 프로그램 시작
