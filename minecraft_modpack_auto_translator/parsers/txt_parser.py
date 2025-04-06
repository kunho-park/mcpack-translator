"""
Txt 파서 클래스

.txt 형식 파일을 처리하는 파서 클래스입니다.
"""

from typing import Any, Dict

from .base_parser import BaseParser


class TxtParser(BaseParser):
    """Txt 형식 파일 파서"""

    @classmethod
    def load(cls, content: str) -> Dict[str, Any]:
        """
        .txt 형식 문자열을 파싱하여 Python 딕셔너리로 반환합니다.
        각 줄은 line_X 형식의 키로 저장됩니다.

        Args:
            content (str): .txt 형식 문자열

        Returns:
            Dict[str, Any]: 파싱된 JSON 데이터
        """
        result = {}
        for i, line in enumerate(content.splitlines()):
            result[f"line_{i}"] = line.strip()
        return result

    @classmethod
    def save(cls, data: Dict[str, Any]) -> str:
        """
        Python 딕셔너리를 .txt 형식 문자열로 변환합니다.
        line_X 형식의 키를 가진 항목을 순서대로 정렬하여 텍스트로 변환합니다.

        Args:
            data (Dict[str, Any]): 변환할 데이터

        Returns:
            str: .txt 형식 문자열
        """
        # line_0, line_1 같은 키를 순서대로 정렬
        sorted_keys = sorted(
            data.keys(),
            key=lambda k: int(k.split("_")[1])
            if k.startswith("line_") and k.split("_")[1].isdigit()
            else 999999,
        )

        result = []
        for key in sorted_keys:
            result.append(str(data[key]))

        return "\n".join(result)
