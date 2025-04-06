"""
XML 파서 클래스

XML 형식 파일을 처리하는 파서 클래스입니다.
"""

import io
import xml.etree.ElementTree as ET
from typing import Any, Dict

from .base_parser import BaseParser


class XMLParser(BaseParser):
    """XML 형식 파일 파서"""

    @classmethod
    def _element_to_dict(cls, element):
        """XML 요소를 사전으로 변환하는 재귀 함수"""
        result = {}

        # 속성 처리
        if element.attrib:
            result["@attributes"] = dict(element.attrib)

        # 텍스트 노드 처리
        if element.text and element.text.strip():
            result["#text"] = element.text.strip()

        # 자식 요소 처리
        children = {}
        for child in element:
            child_dict = cls._element_to_dict(child)

            # 같은 태그 이름을 가진 자식 요소를 리스트로 처리
            if child.tag in children:
                if isinstance(children[child.tag], list):
                    children[child.tag].append(child_dict)
                else:
                    children[child.tag] = [children[child.tag], child_dict]
            else:
                children[child.tag] = child_dict

        if children:
            result.update(children)

        # 특별한 텍스트만 있는 요소는 단순화
        if len(result) == 1 and "#text" in result:
            return result["#text"]

        return result

    @classmethod
    def _dict_to_element(cls, data, tag="root"):
        """사전을 XML 요소로 변환하는 재귀 함수"""
        if isinstance(data, str):
            element = ET.Element(tag)
            element.text = data
            return element

        element = ET.Element(tag)

        # 속성 처리
        if "@attributes" in data:
            for key, value in data["@attributes"].items():
                element.set(key, str(value))
            data_without_attrs = {k: v for k, v in data.items() if k != "@attributes"}
        else:
            data_without_attrs = data

        # 텍스트 노드 처리
        if "#text" in data_without_attrs:
            element.text = data_without_attrs["#text"]
            data_without_attrs = {
                k: v for k, v in data_without_attrs.items() if k != "#text"
            }

        # 자식 요소 처리
        for key, value in data_without_attrs.items():
            if isinstance(value, list):
                # 같은 태그의 여러 요소
                for item in value:
                    element.append(cls._dict_to_element(item, key))
            else:
                # 단일 요소
                element.append(cls._dict_to_element(value, key))

        return element

    @classmethod
    def load(cls, content: str) -> Dict[str, Any]:
        """
        XML 문자열을 파싱하여 Python 딕셔너리로 반환합니다.

        Args:
            content (str): XML 문자열

        Returns:
            Dict[str, Any]: 파싱된 XML 데이터를 딕셔너리로 변환
        """
        try:
            root = ET.fromstring(content)
            result = cls._element_to_dict(root)

            # 최상위 태그를 결과의 키로 사용
            return {root.tag: result}
        except Exception as e:
            raise ValueError(f"XML 파싱 오류: {e}")

    @classmethod
    def save(cls, data: Dict[str, Any]) -> str:
        """
        Python 딕셔너리를 XML 문자열로 변환합니다.

        Args:
            data (Dict[str, Any]): 변환할 데이터

        Returns:
            str: XML 문자열
        """
        if len(data) != 1:
            raise ValueError("XML 데이터는 단일 루트 요소를 가져야 합니다")

        root_tag = next(iter(data))
        root_data = data[root_tag]

        root = cls._dict_to_element(root_data, root_tag)

        # XML 선언 추가 및 문자열로 변환
        tree = ET.ElementTree(root)
        output = io.BytesIO()
        tree.write(output, encoding="UTF-8", xml_declaration=True)

        return output.getvalue().decode("UTF-8")
