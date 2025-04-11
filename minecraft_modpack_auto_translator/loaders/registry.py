import logging
from typing import Any, List

from .base_loader import BaseLoader
from .context import TranslationContext


class LoaderRegistry:
    """
    로더를 등록하고 관리하는 레지스트리 클래스입니다.
    """

    def __init__(self):
        self.loaders: List[BaseLoader] = []
        self.logger = logging.getLogger(__name__)

    def register(self, loader: BaseLoader) -> None:
        """
        새 로더를 등록합니다.

        Args:
            loader: 등록할 로더 인스턴스
        """
        self.loaders.append(loader)
        self.logger.info(f"로더 등록됨: {loader.__class__.__name__}")

    def process_item(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        주어진 경로와 값에 맞는 로더를 찾아 처리합니다.

        Args:
            input_path: JSON 파일 경로
            key: JSON 파일 내 키
            value: 처리할 값
            context: 번역 그래프, 사전 등 컨텍스트 정보

        Returns:
            처리된 값
        """
        for loader in self.loaders:
            if loader.can_handle(input_path, key, value, context):
                self.logger.debug(
                    f"로더 '{loader.__class__.__name__}'가 '{input_path}'의 '{key}'를 처리합니다."
                )
                return loader.process(input_path, key, value, context)

        # 처리 가능한 로더가 없으면 원본 값을 반환
        self.logger.debug(
            f"'{input_path}'의 '{key}'에 대한 적절한 로더를 찾을 수 없습니다."
        )
        return value

    async def aprocess_item(
        self, input_path: str, key: str, value: Any, context: TranslationContext
    ) -> Any:
        """
        주어진 경로와 값에 맞는 로더를 찾아 비동기적으로 처리합니다.

        Args:
            input_path: JSON 파일 경로
            key: JSON 파일 내 키
            value: 처리할 값
            context: 번역 그래프, 사전 등 컨텍스트 정보

        Returns:
            처리된 값
        """
        for loader in self.loaders:
            if loader.can_handle(input_path, key, value, context):
                self.logger.debug(
                    f"비동기 로더 '{loader.__class__.__name__}'가 '{input_path}'의 '{key}'를 처리합니다."
                )
                return await loader.aprocess(input_path, key, value, context)

        # 처리 가능한 로더가 없으면 원본 값을 반환
        self.logger.debug(
            f"'{input_path}'의 '{key}'에 대한 적절한 비동기 로더를 찾을 수 없습니다."
        )
        return value
