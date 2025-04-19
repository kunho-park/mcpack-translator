import os

from minecraft_modpack_auto_translator.parsers.base_parser import BaseParser


def get_supported_extensions():
    """번역 가능한 파일 확장자 목록을 반환합니다."""
    return BaseParser.get_supported_extensions()


def get_parser_by_extension(extension):
    """파일 확장자에 맞는 Parser 클래스를 반환합니다."""
    return BaseParser.get_parser_by_extension(extension)


def extract_lang_content(file_path, content=None):
    """파일 경로 또는 파일객체에서 JSON 파싱된 딕셔너리 데이터를 반환합니다."""
    try:
        if content is None:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        if isinstance(file_path, str):
            ext = os.path.splitext(file_path)[1]
        elif hasattr(file_path, "name"):
            ext = os.path.splitext(file_path.name)[1]
        else:
            raise ValueError(f"Unsupported file identifier: {file_path}")
        parser = get_parser_by_extension(ext)
        if parser:
            return parser.load(content)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
    except Exception:
        raise
