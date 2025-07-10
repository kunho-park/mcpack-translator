import asyncio
import logging
import re
from typing import Any

from .base_loader import BaseLoader
from .context import TranslationContext


class KubeJSScriptLoader(BaseLoader):
    """KubeJS 스크립트 내 displayName 문자열을 처리하는 로더입니다."""

    # ------------------------------------------------------------------
    # 번역 대상 메서드 패턴 정의
    # ------------------------------------------------------------------
    DISPLAY_METHODS = [
        "displayName",
        "formattedDisplayName",
    ]

    # 색상 메서드 (Text.yellow, Component.red 등)
    COLOR_NAMES = [
        "black",
        "darkBlue",
        "darkGreen",
        "darkAqua",
        "darkRed",
        "darkPurple",
        "gold",
        "gray",
        "darkGray",
        "blue",
        "green",
        "aqua",
        "red",
        "lightPurple",
        "yellow",
        "white",
        "of",
    ]

    SECOND_ARG_TRANSLATE_FUNCS = [
        "addTooltip",
    ]

    # 패턴 1: .displayName( "..." ) 형태 (선행 dot 포함)
    _display_pattern = re.compile(
        rf"\.({'|'.join(DISPLAY_METHODS)})\s*\(\s*([\'\"`])((?:[^\\\n]|\\.)*?)\2\s*\)",
        re.MULTILINE,
    )

    # 패턴 2: Text.yellow("...") / Component.blue(`...`) 형태 (선행 dot 없음)
    _color_pattern = re.compile(
        rf"((?:Text|Component)\.({'|'.join(COLOR_NAMES)}))\s*\(\s*([\'\"`])((?:[^\\\n]|\\.)*?)\3\s*\)",
        re.MULTILINE,
    )

    # 패턴 3: addTooltip('id', 'text', ...)
    _second_arg_pattern = re.compile(
        rf"({'|'.join(SECOND_ARG_TRANSLATE_FUNCS)})\s*\(([^,]+?),\s*([\'\"`])((?:[^\\]|\\.)*?)\3(\s*(?:,[^)]*)?)\)",
        re.DOTALL,
    )

    # 패턴 목록
    PATTERNS = [_display_pattern, _color_pattern, _second_arg_pattern]

    # ------------------------------------------------------------------
    # 내부 유틸리티
    # ------------------------------------------------------------------
    @staticmethod
    def _escape_literal(orig: str, trans: str, quote_char: str) -> str:
        """번역된 문자열에서 개행과 따옴표를 원본 스타일로 이스케이프합니다."""
        # 번역 결과에 양쪽 따옴표가 그대로 포함된 경우 제거
        if trans.startswith(quote_char) and trans.endswith(quote_char):
            trans = trans[1:-1]
        if "\\n" in orig and "\n" in trans and "\\n" not in trans:
            trans = trans.replace("\n", "\\n")
        # 번역 결과에 새 개행이 추가되었는데 원본에는 없을 때: 공백으로 대체
        if "\n" in trans and "\n" not in orig and "\\n" not in orig:
            trans = trans.replace("\n", " ")
        # 추가 이스케이프는 하지 않음 (불필요한 역슬래시 삽입 방지)
        trans = trans.replace("\n", "\\n")
        return trans

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ---------------------------------------------------------------------
    # BaseLoader 인터페이스 구현
    # ---------------------------------------------------------------------
    def can_handle(
        self,
        input_path: str,
        key: str,
        value: Any,
        context: TranslationContext,
    ) -> bool:
        """/kubejs/ 경로의 .js 파일 청크/라인에서 displayName 호출이 있는지 확인합니다."""
        if not (
            isinstance(value, str)
            and "/kubejs/" in input_path.replace("\\", "/")
            and (
                input_path.lower().endswith(".js.converted")
                or input_path.lower().endswith(".js")
            )
        ):
            return False

        # chunk_X 혹은 line_X 키 또는 JSParser의 'content' 키
        if not (
            key.startswith("chunk_") or key.startswith("line_") or key == "content"
        ):
            return False

        # 패턴 존재 여부와 관계없이 .js.converted 파일은 이 로더가 처리
        # (다른 로더가 주석 등을 번역하지 못하도록)
        return True

    # ---------------------------- 동기 처리 ------------------------------
    def process(
        self,
        input_path: str,
        key: str,
        value: Any,
        context: TranslationContext,
    ) -> Any:
        """displayName 내부의 문자열을 번역합니다 (동기)."""
        translation_graph = context.translation_graph
        custom_dictionary_dict = context.custom_dictionary_dict

        # 번역 그래프가 없거나 displayName이 없으면 원본 반환
        if not translation_graph:
            return value

        # 패턴이 하나도 없으면 그대로 반환하여 주석 등이 번역되지 않도록 함
        if not any(p.search(value) for p in self.PATTERNS):
            return value

        processed = value

        def _translate(
            match: re.Match,
            method_group_index: int,
            quote_index: int,
            text_index: int,
            prefix_dot: bool = False,
        ):
            quote = match.group(quote_index)
            original_text = match.group(text_index)
            method_name = match.group(method_group_index)
            translated = original_text
            try:
                state = translation_graph.invoke(
                    {
                        "text": original_text,
                        "custom_dictionary_dict": custom_dictionary_dict,
                        "context": context,
                    }
                )
                translated = state["restored_text"]
                translated = self._escape_literal(original_text, translated, quote)
            except Exception as e:
                self.logger.error(
                    f"KubeJS 스크립트 번역 오류: {e} | 원본: {original_text}"
                )
            dot = "." if prefix_dot else ""
            return f"{dot}{method_name}({quote}{translated}{quote})"

        # displayName 계열 (.displayName)
        processed = self._display_pattern.sub(
            lambda m: _translate(m, 1, 2, 3, prefix_dot=True), processed
        )

        # Text/Component 색상 메서드
        processed = self._color_pattern.sub(lambda m: _translate(m, 1, 3, 4), processed)

        def _translate_second_arg(match: re.Match):
            func_name = match.group(1)
            arg1 = match.group(2)
            quote = match.group(3)
            original_text = match.group(4)
            rest = match.group(5)
            translated = original_text
            try:
                state = translation_graph.invoke(
                    {
                        "text": original_text,
                        "custom_dictionary_dict": custom_dictionary_dict,
                        "context": context,
                    }
                )
                translated = state["restored_text"]
                translated = self._escape_literal(original_text, translated, quote)
            except Exception as e:
                self.logger.error(
                    f"KubeJS 스크립트 번역 오류: {e} | 원본: {original_text}"
                )
            return f"{func_name}({arg1},{quote}{translated}{quote}{rest})"

        processed = self._second_arg_pattern.sub(_translate_second_arg, processed)

        return processed

    # --------------------------- 비동기 처리 -----------------------------
    async def aprocess(
        self,
        input_path: str,
        key: str,
        value: Any,
        context: TranslationContext,
        llm=None,
    ) -> Any:
        """displayName 내부의 문자열을 비동기 번역합니다."""
        translation_graph = context.translation_graph
        custom_dictionary_dict = context.custom_dictionary_dict

        if not translation_graph:
            return value, False

        has_error = False

        async def _a_translate(
            match: re.Match,
            method_group_index: int,
            quote_index: int,
            text_index: int,
            prefix_dot: bool = False,
        ):
            nonlocal has_error
            quote = match.group(quote_index)
            original_text = match.group(text_index)
            method_name = match.group(method_group_index)
            translated = original_text
            try:
                state = await translation_graph.ainvoke(
                    {
                        "text": original_text,
                        "custom_dictionary_dict": custom_dictionary_dict,
                        "llm": llm,
                        "context": context,
                        "translation_key": key,
                    }
                )
                translated = state["restored_text"]
                translated = self._escape_literal(original_text, translated, quote)
                has_error = has_error or state.get("has_error", False)
            except Exception as e:
                has_error = True
                self.logger.error(
                    f"KubeJS 스크립트 비동기 번역 오류: {e} | 원본: {original_text}"
                )
            dot = "." if prefix_dot else ""
            return f"{dot}{method_name}({quote}{translated}{quote})"

        async def _a_translate_second_arg(match: re.Match):
            nonlocal has_error
            func_name = match.group(1)
            arg1 = match.group(2)
            quote = match.group(3)
            original_text = match.group(4)
            rest = match.group(5)
            translated = original_text

            try:
                state = await translation_graph.ainvoke(
                    {
                        "text": original_text,
                        "custom_dictionary_dict": custom_dictionary_dict,
                        "llm": llm,
                        "context": context,
                        "translation_key": key,
                    }
                )
                translated = state["restored_text"]
                translated = self._escape_literal(original_text, translated, quote)
                has_error = has_error or state.get("has_error", False)
            except Exception as e:
                has_error = True
                self.logger.error(
                    f"KubeJS 스크립트 비동기 번역 오류: {e} | 원본: {original_text}"
                )
            return f"{func_name}({arg1}, {quote}{translated}{quote}{rest})"

        # 동기와 달리 비동기 치환은 수동 수행해야 여러 await 가능
        async def async_substitute(pattern: re.Pattern, repl, text: str):
            result_parts = []
            last_idx = 0
            for m in pattern.finditer(text):
                result_parts.append(text[last_idx : m.start()])
                replacement = repl(m)
                if asyncio.iscoroutine(replacement):
                    replacement = await replacement
                result_parts.append(replacement)
                last_idx = m.end()
            result_parts.append(text[last_idx:])
            return "".join(result_parts)

        # 패턴이 없으면 그대로 반환
        if not any(p.search(value) for p in self.PATTERNS):
            return value, False

        # 1) .displayName 계열
        processed = await async_substitute(
            self._display_pattern,
            lambda m: _a_translate(m, 1, 2, 3, prefix_dot=True),
            value,
        )

        # 2) Text/Component 색상 메서드
        processed = await async_substitute(
            self._color_pattern, lambda m: _a_translate(m, 1, 3, 4), processed
        )

        # 3) addTooltip 등 2번째 인자 번역
        processed = await async_substitute(
            self._second_arg_pattern, _a_translate_second_arg, processed
        )

        return processed, has_error
