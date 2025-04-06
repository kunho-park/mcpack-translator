import json
from typing import Dict, Union


class MCLangParser:
    """
    Minecraft .lang 파일 파서
    .lang 파일을 파싱하고 JSON으로 변환하거나, JSON을 .lang 파일 형식으로 변환합니다.
    """

    @staticmethod
    def parse_lang_file(file_path: str) -> Dict[str, str]:
        """
        .lang 파일을 파싱하여 딕셔너리로 변환합니다.

        Args:
            file_path: .lang 파일 경로

        Returns:
            키-값 쌍으로 이루어진 딕셔너리
        """
        translations = {}

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # 주석 또는 빈 줄 무시
                if not line or line.startswith("#"):
                    continue

                # key=value 형식 파싱
                if "=" in line:
                    key, value = line.split("=", 1)
                    translations[key.strip()] = value.strip()

        return translations

    @staticmethod
    def convert_to_json(lang_data: Dict[str, str], output_file: str = None) -> str:
        """
        파싱된 .lang 데이터를 JSON 문자열로 변환합니다.

        Args:
            lang_data: 파싱된 .lang 데이터
            output_file: JSON 파일을 저장할 경로 (선택사항)

        Returns:
            JSON 문자열
        """
        json_str = json.dumps(lang_data, ensure_ascii=False, indent=2)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(json_str)

        return json_str

    @staticmethod
    def convert_from_json(
        json_data: Union[str, Dict[str, str]], output_file: str = None
    ) -> str:
        """
        JSON 데이터를 .lang 파일 형식으로 변환합니다.

        Args:
            json_data: JSON 문자열 또는 딕셔너리
            output_file: .lang 파일을 저장할 경로 (선택사항)

        Returns:
            .lang 파일 형식의 문자열
        """
        # JSON 문자열이면 딕셔너리로 변환
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        # .lang 파일 형식으로 변환
        lang_lines = []
        for key, value in data.items():
            lang_lines.append(f"{key}={value}")

        lang_content = "\n".join(lang_lines)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(lang_content)

        return lang_content

    @staticmethod
    def load_json_file(file_path: str) -> Dict[str, str]:
        """
        JSON 파일을 로드합니다.

        Args:
            file_path: JSON 파일 경로

        Returns:
            JSON 데이터를 담은 딕셔너리
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)


def lang_to_json(input_file: str, output_file: str = None) -> Dict[str, str]:
    """
    .lang 파일을 JSON 파일로 변환합니다.

    Args:
        input_file: 입력 .lang 파일 경로
        output_file: 출력 JSON 파일 경로 (선택사항)

    Returns:
        변환된 데이터를 담은 딕셔너리
    """
    parser = MCLangParser()
    lang_data = parser.parse_lang_file(input_file)

    if output_file:
        parser.convert_to_json(lang_data, output_file)

    return lang_data


def json_to_lang(input_file: str, output_file: str) -> str:
    """
    JSON 파일을 .lang 파일로 변환합니다.

    Args:
        input_file: 입력 JSON 파일 경로
        output_file: 출력 .lang 파일 경로

    Returns:
        변환된 .lang 파일 내용
    """
    parser = MCLangParser()
    json_data = parser.load_json_file(input_file)
    return parser.convert_from_json(json_data, output_file)
