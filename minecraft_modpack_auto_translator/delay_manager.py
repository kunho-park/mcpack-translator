import asyncio
import logging
import threading  # Import threading for the init lock
import time
from typing import Optional

# 로거 설정
logger = logging.getLogger(__name__)


class DelayManager:
    """
    API 요청 사이에 지연 시간을 관리하는 클래스
    여러 워커에서 공유하여 사용할 수 있도록 설계됨
    """

    _init_lock = threading.Lock()  # Lock for initializing the asyncio lock

    def __init__(self, delay: float = 0.5):
        """
        딜레이 관리자 초기화

        Args:
            delay: 요청 사이의 지연 시간 (초 단위)
        """

        self.delay = delay  # 기본 딜레이 (초)
        self.last_request_time = 0.0  # 마지막 요청 시간
        self.lock: Optional[asyncio.Lock] = None  # asyncio.Lock을 None으로 초기화
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

    async def _get_or_create_lock(self) -> asyncio.Lock:
        """asyncio.Lock이 없으면 지연 생성합니다."""
        if self.lock is None:
            # threading.Lock을 사용하여 asyncio.Lock 생성을 보호
            with DelayManager._init_lock:
                # Double-check locking 패턴
                if self.lock is None:
                    logger.debug("DelayManager를 위한 asyncio.Lock 초기화 중.")
                    # 특정 루프를 지정하지 않고 락 생성
                    self.lock = asyncio.Lock()
        # None이 아님을 명시 (타입 힌트 만족)
        assert self.lock is not None
        return self.lock

    async def wait_before_request(self) -> None:
        """
        요청 전 필요한 딜레이만큼 대기
        """
        lock = await self._get_or_create_lock()  # 락 가져오기 또는 생성
        async with lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time

            # 필요한 만큼만 대기
            if elapsed < self.delay and self.last_request_time > 0:
                wait_time = self.delay - elapsed
                logger.debug(f"API 요청 전 {wait_time:.2f}초 대기 중")
                await asyncio.sleep(wait_time)

            # 마지막 요청 시간 업데이트 (락 내부에서)
            self.last_request_time = time.time()

    async def wait_after_request(
        self, additional_delay: Optional[float] = None
    ) -> None:
        """
        요청 후 필요한 딜레이만큼 대기 (옵션: 추가 딜레이)

        Args:
            additional_delay: 기본 딜레이에 추가할 딜레이 시간 (초 단위)
        """
        lock = await self._get_or_create_lock()  # 락 가져오기 또는 생성

        total_delay = self.delay + (additional_delay or 0)

        if total_delay > 0:
            logger.debug(f"API 요청 후 {total_delay:.2f}초 대기 중")
            await asyncio.sleep(total_delay)

        # 마지막 요청 시간 업데이트 (락 내부에서)
        async with lock:
            self.last_request_time = time.time()
