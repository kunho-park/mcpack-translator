"""
SNBT 파서 클래스

.snbt 형식 파일을 처리하는 파서 클래스입니다.
"""

import re
from typing import Any, Dict

import ftb_snbt_lib as slib
from ftb_snbt_lib.tag import Bool, Compound, Double, Integer, Long, String
from ftb_snbt_lib.tag import List as SNBTList

from .base_parser import BaseParser


class SNBTParser(BaseParser):
    """SNBT 형식 파일 파서"""

    @staticmethod
    def     replace_ampersand(obj):
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
            return re.sub(pattern, r"\\&", re.sub(r"\n", r"\\n", obj))
        elif isinstance(obj, dict):
            return {k: SNBTParser.replace_ampersand(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [SNBTParser.replace_ampersand(item) for item in obj]
        else:
            return obj

    @staticmethod
    def is_valid_snbt_key(key: str) -> bool:
        """
        SNBT 키가 따옴표 없이 사용할 수 있는 유효한 문자만 포함하는지 확인합니다.
        유효한 문자: 0-9, A-Z, a-z, _, -, ., +

        Args:
            key: 확인할 키 문자열

        Returns:
            bool: 키가 유효한 문자만 포함하는 경우 True, 그렇지 않으면 False
        """
        return bool(re.match(r"^[0-9A-Za-z_\-\.+]+$", key))

    @staticmethod
    def format_snbt_key(key: str) -> str:
        """
        SNBT 키를 적절한 형식으로 변환합니다.
        콜론(:)이 포함된 경우 따옴표로 묶습니다.

        Args:
            key: 변환할 키 문자열

        Returns:
            str: 변환된 키 문자열
        """
        if ":" in key or not SNBTParser.is_valid_snbt_key(key):
            return f'"{key}"'
        return key

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

    @staticmethod
    def convert_to_snbt_type(value: Any) -> Any:
        """
        Python 값을 해당하는 SNBT 데이터 타입으로 변환합니다.

        Args:
            value: 변환할 Python 값

        Returns:
            SNBT 데이터 타입으로 변환된 값
        """
        if isinstance(value, bool):
            return Bool(value)
        elif isinstance(value, int):
            # 범위에 따라 적절한 정수 타입 사용
            if -2147483648 <= value <= 2147483647:
                return Integer(value)
            else:
                return Long(value)
        elif isinstance(value, float):
            # 기본적으로 Double 사용 (정밀도 유지)
            return Double(value)
        elif isinstance(value, str):
            return String(value)
        elif isinstance(value, list):
            if len(value) == 0:
                return SNBTList([])

            # 리스트 요소들을 SNBT 타입으로 변환
            converted_items = [SNBTParser.convert_to_snbt_type(item) for item in value]
            return SNBTList(converted_items)
        elif isinstance(value, dict):
            # 딕셔너리 내 모든 값을 SNBT 타입으로 변환
            snbt_dict = {}
            for k, v in value.items():
                # 키가 문자열이 아니면 문자열로 변환
                if not isinstance(k, str):
                    k = str(k)

                # 키 형식 변환 (콜론이 포함된 경우 따옴표로 묶음)
                formatted_key = SNBTParser.format_snbt_key(k)

                # 값을 SNBT 타입으로 변환
                snbt_dict[formatted_key] = SNBTParser.convert_to_snbt_type(v)

            return Compound(snbt_dict)
        else:
            # 변환할 수 없는 타입은 문자열로 처리
            return String(str(value))

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
        processed_data = cls.replace_ampersand(data)

        # Python 데이터를 SNBT 타입으로 변환
        snbt_data = cls.convert_to_snbt_type(processed_data)

        # SNBT 문자열로 덤프
        return slib.dumps(snbt_data)
