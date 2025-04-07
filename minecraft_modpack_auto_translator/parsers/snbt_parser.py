"""
SNBT 파서 클래스

.snbt 형식 파일을 처리하는 파서 클래스입니다.
"""

import json
import re
from typing import Any, Dict

import ftb_snbt_lib as slib

from .base_parser import BaseParser


class SNBTParser(BaseParser):
    """SNBT 형식 파일 파서"""

    @staticmethod
    def replace_ampersand(obj):
        """
        객체 내의 & 문자를 이스케이프 처리합니다 (마인크래프트 컬러 코드 제외).

        Args:
            obj: 처리할 객체 (문자열, 딕셔너리, 리스트)

        Returns:
            처리된 객체
        """
        if isinstance(obj, str):
            # 마크 컬러코드 형식(&0~&9, &a~&f, &k~&o, &r)은 치환하지 않고 유지
            # 컬러코드가 아닌 &만 이스케이프 처리
            pattern = r"&(?![0-9a-fk-or])"
            return re.sub(pattern, r"\\&", obj)
        elif isinstance(obj, dict):
            return {k: SNBTParser.replace_ampersand(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [SNBTParser.replace_ampersand(item) for item in obj]
        else:
            return obj

    @classmethod
    def load(cls, content: str) -> Dict[str, Any]:
        """
        .snbt 형식 문자열을 파싱하여 Python 딕셔너리로 반환합니다.

        Args:
            content (str): .snbt 형식 문자열

        Returns:
            Dict[str, Any]: 파싱된 JSON 데이터
        """
        return slib.loads(content)

    @classmethod
    def save(cls, data: Dict[str, Any]) -> str:
        """
        Python 딕셔너리를 .snbt 형식 문자열로 변환합니다.

        Args:
            data (Dict[str, Any]): 변환할 데이터

        Returns:
            str: .snbt 형식 문자열
        """
        # & 문자 치환 적용
        json_data = cls.replace_ampersand(data)

        json_str = json.dumps(json_data, ensure_ascii=False)

        return slib.dumps(json_str)
