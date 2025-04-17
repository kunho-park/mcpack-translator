import streamlit as st

home_page = st.Page("home.py", title="홈", icon="🏠")
modpack_page = st.Page(
    "translate_ui/1_Modpack_Translator.py", title="원클릭 모드팩 번역기", icon="🌐"
)
file_page = st.Page(
    "translate_ui/2_File_Translator.py", title="단일 파일 번역기", icon="📄"
)
txt_page = st.Page("translate_ui/3_Txt_Translator.py", title="텍스트 번역기", icon="✏️")
# 네비게이션 설정
page_navigation = st.navigation(
    {"메인": [home_page], "번역": [modpack_page, file_page, txt_page]}
)

page_navigation.run()
