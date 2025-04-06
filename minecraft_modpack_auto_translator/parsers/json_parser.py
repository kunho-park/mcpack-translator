"""
JSON 파서 클래스

JSON 형식 파일을 처리하는 파서 클래스입니다.
"""

import json
import re
from typing import Any, Dict

from .base_parser import BaseParser


class JSONParser(BaseParser):
    """JSON 형식 파일 파서"""

    # JSON 파일에서 주석 제거하는 정규식 패턴
    # // 형식의 한 줄 주석을 제거합니다
    COMMENT_PATTERN = re.compile(r"^\s*//.*$|//.*$", re.MULTILINE)

    @classmethod
    def load(cls, content: str) -> Dict[str, Any]:
        """
        JSON 문자열을 파싱하여 Python 딕셔너리로 반환합니다.
        주석이 포함된 JSON도 처리할 수 있습니다.

        Args:
            content (str): JSON 문자열

        Returns:
            Dict[str, Any]: 파싱된 JSON 데이터
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 주석이 있는 경우 주석 제거 후 다시 시도
            try:
                cleaned_content = cls.COMMENT_PATTERN.sub("", content)
                return json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON 파싱 오류: {e}")

    @classmethod
    def save(cls, data: Dict[str, Any]) -> str:
        """
        Python 딕셔너리를 JSON 문자열로 변환합니다.

        Args:
            data (Dict[str, Any]): 변환할 데이터

        Returns:
            str: JSON 문자열
        """
        return json.dumps(data, ensure_ascii=False, indent=4)
