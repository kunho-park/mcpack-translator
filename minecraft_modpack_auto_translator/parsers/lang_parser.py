"""
Lang 파서 클래스

.lang 형식 파일을 처리하는 파서 클래스입니다.
"""

import json
from typing import Any, Dict

from .base_parser import BaseParser


class LangParser(BaseParser):
    """Lang 형식 파일 파서"""

    @classmethod
    def load(cls, content: str) -> Dict[str, Any]:
        """
        .lang 형식 문자열을 파싱하여 Python 딕셔너리로 반환합니다.

        Args:
            content (str): .lang 형식 문자열

        Returns:
            Dict[str, Any]: 파싱된 JSON 데이터
        """
        result = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                # JSON 이스케이프 처리를 통해 특수 문자 처리
                if isinstance(value, str):
                    try:
                        parsed_value = json.loads(f'"{value.strip()}"')
                    except json.JSONDecodeError:
                        parsed_value = value.strip()
                else:
                    parsed_value = value.strip()
                result[key.strip()] = parsed_value
        return result

    @classmethod
    def save(cls, data: Dict[str, Any]) -> str:
        """
        Python 딕셔너리를 .lang 형식 문자열로 변환합니다.

        Args:
            data (Dict[str, Any]): 변환할 데이터

        Returns:
            str: .lang 형식 문자열
        """
        result = []
        for key, value in data.items():
            # JSON 이스케이프 처리를 통해 특수 문자 처리
            if isinstance(value, str):
                escaped_value = json.dumps(value, ensure_ascii=False)[
                    1:-1
                ]  # 따옴표 제거
            else:
                escaped_value = str(value)
            result.append(f"{key}={escaped_value}")
        return "\n".join(result)
