"""
기본 파서 클래스

모든 파서의 기본 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type, Union


class BaseParser(ABC):
    """
    기본 파서 클래스. 모든 특정 파일 형식 파서는 이 클래스를 상속받아야 합니다.
    """

    @classmethod
    @abstractmethod
    def load(cls, content: str) -> Dict[str, Any]:
        """
        파일 내용을 로드하여 JSON 형태의 데이터로 변환합니다.

        Args:
            content (str): 파일 내용

        Returns:
            Dict[str, Any]: 파싱된 JSON 데이터
        """
        pass

    @classmethod
    @abstractmethod
    def save(cls, data: Dict[str, Any]) -> str:
        """
        JSON 데이터를 파일 형식에 맞는 문자열로 변환합니다.

        Args:
            data (Dict[str, Any]): 변환할 JSON 데이터

        Returns:
            str: 변환된 파일 내용
        """
        pass

    @staticmethod
    def get_parser_by_extension(extension: str) -> Union[Type["BaseParser"], None]:
        """
        파일 확장자에 따라 적절한 파서를 반환합니다.

        Args:
            extension (str): 파일 확장자 (.json, .lang, .txt, .snbt, .xml 등)

        Returns:
            BaseParser: 해당 확장자에 맞는 파서 클래스
        """
        extension = extension.lower()

        # 동적으로 임포트하여 순환 참조 해결
        if extension == ".json":
            from .json_parser import JSONParser

            return JSONParser
        elif extension == ".lang":
            from .lang_parser import LangParser

            return LangParser
        elif extension == ".txt":
            from .txt_parser import TxtParser

            return TxtParser
        elif extension == ".snbt":
            from .snbt_parser import SNBTParser

            return SNBTParser
        elif extension == ".xml":
            from .xml_parser import XMLParser

            return XMLParser
        else:
            return None

    @staticmethod
    def get_supported_extensions() -> List[str]:
        """
        지원하는 파일 확장자 목록을 반환합니다.

        Returns:
            List[str]: 지원하는 파일 확장자 목록
        """
        return [".json", ".lang", ".txt", ".snbt", ".xml"]
