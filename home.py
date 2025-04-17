import streamlit as st

st.set_page_config(
    page_title="마인크래프트 모드팩 자동 번역기",
    page_icon="🌍",
    layout="wide",
)

st.title("🌍 마인크래프트 모드팩 자동 번역기")

st.markdown(
    """
    마인크래프트 모드팩을 영어에서 한국어로 자동 번역하는 도구입니다.
    마인크래프트 공식 번역 데이터를 활용한 RAG(Retrieval-Augmented Generation)를 통해
    고유명사와 포맷 코드를 보존하면서 자연스러운 번역을 제공합니다.
    
    Github ⭐️(Star) 눌러주시면 감사하겠습니다!

    **⚠️ 중요: 이 도구를 사용하려면 아래 지원되는 LLM 서비스 중 하나의 API 키 또는 로컬 설정(Ollama API)이 필요합니다.**
    """
)

# GitHub 링크 (아이콘 추가) - Star 눌러주시면 감사하겠습니다!
st.markdown(
    "🐙 [GitHub 저장소 (⭐️ 눌러주세요!)](https://github.com/kunho-park/mcpack-translator)"
)

st.header("✨ 주요 기능")
st.markdown(
    """
    - 마인크래프트 모드팩 JSON, LANG, SNBT 파일 번역
    - 플레이스홀더(%s, %d 등) 보존
    - 포맷 코드(§) 보존
    - 대형 언어 모델(LLM)을 활용한 자연스러운 번역
    - 고유명사 및 게임 용어 정확한 번역
    """
)

st.header("🔑 지원하는 LLM 서비스")
st.markdown(
    """
    번역 기능을 사용하려면 다음 LLM 서비스 중 하나를 선택하여 설정해야 합니다:

    - **G4F (GPT4Free)**: 무료 옵션 (API 키 불필요, 속도 제한 및 안정성 주의)
    - **OpenAI**: GPT 모델 (API 키 필요)
    - **Google**: Gemini 모델 (API 키 필요)
    - **Grok**: Grok 모델 (API 키 필요)
    - **Ollama**: 로컬 LLM 모델 실행 (로컬 서버 설정 필요)
    - **Anthropic**: Claude 모델 (API 키 필요)

    각 서비스 사용에 필요한 설정은 사이드바에서 진행할 수 있습니다.
    """
)
