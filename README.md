# 마인크래프트 모드팩 자동 번역기

마인크래프트 모드팩을 영어에서 한국어로 자동 번역하는 도구입니다. 마인크래프트 공식 번역 데이터를 활용한 RAG(Retrieval-Augmented Generation)를 통해 고유명사와 포맷 코드를 보존하면서 자연스러운 번역을 제공합니다.

## 주요 기능

- 마인크래프트 모드팩 JSON, LANG, SNBT 파일 번역
- 플레이스홀더(%s, %d 등) 보존
- 포맷 코드(§) 보존
- 대형 언어 모델(LLM)을 활용한 자연스러운 번역
- 고유명사 및 게임 용어 정확한 번역
- GUI 인터페이스 제공

## 설치

### 요구 사항
- Python 3.12 이상
- OpenAI API 키, Anthropic API 키, Google AI API 키 중 하나 이상

### 윈도우 자동 설치 방법

현재 자동 설치는 윈도우 환경에서만 지원됩니다.

### 설치 전 필수 프로그램

프로그램을 설치하기 전에 다음 프로그램이 필요합니다:

1. **Git**: [Git 다운로드 페이지](https://git-scm.com/downloads/win)에서 설치 파일을 다운로드하여 설치합니다.
2. **uv**: [uv 설치 가이드](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_2)를 참고하여 설치합니다.

위 프로그램들이 설치되어 있어야 자동 설치 스크립트가 정상적으로 작동합니다.

### 설치 절차

1. [mcpack-translator-win.zip](https://github.com/kunho-park/mcpack-translator/releases/download/setup/mcpack-translator-win.zip) 파일을 다운로드합니다.
2. 압축을 풀고 `update.bat` 파일을 실행하여 최신 버전으로 업데이트합니다.
3. `run.bat` 파일을 실행하여 프로그램을 시작합니다.
   (이후 실행 시에는 업데이트가 필요 없다면 `run.bat`만 실행하면 됩니다.)

### 수동 설치
```bash
# 가상 환경 생성 및 활성화
uv sync
```

## 환경 설정

`.env` 파일에 API 키를 설정하세요:
```
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
```

## 사용 방법

### GUI 인터페이스 사용

GUI 인터페이스를 시작하려면:

```bash
# Windows에서 GUI 실행
run.bat

# 또는 직접 실행
python gui.py
```

GUI를 통해 다음 작업을 수행할 수 있습니다:
- 모드팩 파일 선택 및 번역
- 리소스팩 생성
- 번역 모델 및 옵션 설정
- 번역 기록 확인 및 관리

## 지원하는 파일 형식

- JSON: 대부분의 모드팩 언어 파일
- LANG: 구버전 마인크래프트 언어 파일
- SNBT: FTB 퀘스트 및 기타 데이터 파일

## 커스터마이징

`minecraft_modpack_auto_translator/config.py` 파일에서 다음 설정을 조정할 수 있습니다:

- 번역 모델 및 파라미터
- 포맷 코드 및 플레이스홀더 처리 방식
- 파일 처리 옵션
- GUI 기본 설정

## 라이센스

MIT
