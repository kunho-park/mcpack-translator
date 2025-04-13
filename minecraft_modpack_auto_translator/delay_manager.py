import asyncio
import logging
import time
from typing import Optional

# 로거 설정
logger = logging.getLogger(__name__)


class DelayManager:
    """
    API 요청 사이에 지연 시간을 관리하는 클래스
    여러 워커에서 공유하여 사용할 수 있도록 설계됨
    """

    _instance = None  # 싱글톤 인스턴스

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DelayManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, delay: float = 0.5):
        """
        딜레이 관리자 초기화

        Args:
            delay: 요청 사이의 지연 시간 (초 단위)
        """
        # 이미 초기화된 경우 중복 초기화 방지
        if self._initialized:
            return

        self.delay = delay  # 기본 딜레이 (초)
        self.last_request_time = 0.0  # 마지막 요청 시간
        self.lock = asyncio.Lock()  # 동시 접근 방지를 위한 락
        self._initialized = True
        logger.info(f"딜레이 관리자 초기화: {delay}초")

    def set_delay(self, delay: float) -> None:
        """
        딜레이 시간 설정

        Args:
            delay: 설정할 지연 시간 (초 단위)
        """
        if delay < 0:
            delay = 0
        self.delay = delay
        logger.info(f"딜레이 시간 변경: {delay}초")

    def get_delay(self) -> float:
        """
        현재 설정된 딜레이 시간 반환

        Returns:
            현재 설정된 딜레이 시간 (초 단위)
        """
        return self.delay

    async def wait_before_request(self) -> None:
        """
        요청 전 필요한 딜레이만큼 대기
        """
        async with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time

            # 필요한 만큼만 대기
            if elapsed < self.delay and self.last_request_time > 0:
                wait_time = self.delay - elapsed
                logger.debug(f"API 요청 전 {wait_time:.2f}초 대기 중")
                await asyncio.sleep(wait_time)

            # 마지막 요청 시간 업데이트
            self.last_request_time = time.time()

    async def wait_after_request(
        self, additional_delay: Optional[float] = None
    ) -> None:
        """
        요청 후 필요한 딜레이만큼 대기 (옵션: 추가 딜레이)

        Args:
            additional_delay: 기본 딜레이에 추가할 딜레이 시간 (초 단위)
        """
        if additional_delay is None:
            additional_delay = 0

        total_delay = self.delay + additional_delay

        if total_delay > 0:
            logger.debug(f"API 요청 후 {total_delay:.2f}초 대기 중")
            await asyncio.sleep(total_delay)

        # 마지막 요청 시간 업데이트
        async with self.lock:
            self.last_request_time = time.time()
