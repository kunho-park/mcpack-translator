from typing import Any, Dict

from .base_parser import BaseParser


class JSParser(BaseParser):
    """단순 JS 파일 파서.

    파일 전체 내용을 하나의 "content" 키로 보관하여 절대 분할되지 않도록 합니다.
    """

    @classmethod
    def load(cls, content: str) -> Dict[str, Any]:
        # JS 파일은 별도 구조가 없으므로 전체 내용을 단일 문자열로 반환
        return {"content": content}

    @classmethod
    def save(cls, data: Dict[str, Any]) -> str:
        # 저장 시 "content" 키가 있으면 반환, 없으면 빈 문자열
        return str(data.get("content", ""))
