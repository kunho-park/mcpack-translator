"""
마크다운 파서 클래스

.md 형식 파일을 처리하는 파서 클래스입니다.
"""

from typing import Any, Dict

from .base_parser import BaseParser


class MarkdownParser(BaseParser):
    """마크다운 형식 파일 파서"""

    @classmethod
    def load(cls, content: str) -> Dict[str, Any]:
        """
        .md 형식 문자열을 파싱하여 Python 딕셔너리로 반환합니다.
        줄 바꿈을 기준으로 최대 2000자 이내의 청크로 나누어 저장합니다.

        Args:
            content (str): .md 형식 문자열

        Returns:
            Dict[str, Any]: 파싱된 JSON 데이터
        """
        result = {}
        lines = content.splitlines()
        chunk_idx = 0
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line)

            # 청크가 비어있지 않고, 현재 줄을 추가하면 2000자를 초과할 경우 새 청크 시작
            if current_chunk and current_length + line_length > 2000:
                result[f"chunk_{chunk_idx}"] = "\n".join(current_chunk)
                chunk_idx += 1
                current_chunk = []
                current_length = 0

            current_chunk.append(line)
            current_length += line_length

        # 마지막 청크 저장
        if current_chunk:
            result[f"chunk_{chunk_idx}"] = "\n".join(current_chunk)

        return result

    @classmethod
    def save(cls, data: Dict[str, Any]) -> str:
        """
        Python 딕셔너리를 .md 형식 문자열로 변환합니다.
        chunk_X 형식의 키를 가진 항목을 순서대로 정렬하여 텍스트로 변환합니다.

        Args:
            data (Dict[str, Any]): 변환할 데이터

        Returns:
            str: .md 형식 문자열
        """
        # chunk_0, chunk_1 같은 키를 순서대로 정렬
        sorted_keys = sorted(
            data.keys(),
            key=lambda k: int(k.split("_")[1])
            if k.startswith("chunk_") and k.split("_")[1].isdigit()
            else 999999,
        )

        result = []
        for key in sorted_keys:
            result.append(str(data[key]))

        return "\n".join(result)
