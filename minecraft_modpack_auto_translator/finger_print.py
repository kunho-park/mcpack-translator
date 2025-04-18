from typing import Union

import aiofiles
import numpy as np
from numba import njit


@njit(nogil=True)
def _compute_fingerprint_nb(buf):
    # 상수
    MULT = np.uint32(1540483477)
    MASK = np.uint32(0xFFFFFFFF)

    # 1) 공백 제외 길이 세기
    normalized = np.uint32(0)
    for b in buf:
        if b != 9 and b != 10 and b != 13 and b != 32:
            normalized += np.uint32(1)

    # 2) 해시 초기화
    num2 = np.uint32(1) ^ normalized
    num3 = np.uint32(0)
    num4 = 0  # 비트 오프셋

    # 3) 메인 루프
    for b in buf:
        if b != 9 and b != 10 and b != 13 and b != 32:
            num3 |= np.uint32(b) << num4
            num4 += 8
            if num4 == 32:
                num6 = (num3 * MULT) & MASK
                num7 = ((num6 ^ (num6 >> 24)) * MULT) & MASK
                num2 = ((num2 * MULT) ^ num7) & MASK
                num3 = np.uint32(0)
                num4 = 0

    # 4) 남은 비트 처리
    if num4 > 0:
        num2 = ((num2 ^ num3) * MULT) & MASK

    # 5) 최종 믹스
    num6 = ((num2 ^ (num2 >> 13)) * MULT) & MASK
    return (num6 ^ (num6 >> 15)) & MASK


def compute_fingerprint(data: Union[bytes, bytearray]) -> int:
    """
    바이트 시퀀스에 대해 fingerprint 계산.
    """
    # frombuffer 로 읽기 전용 뷰가 생성되므로, .copy() 로 복사해서 쓰기 가능하게 만듭니다.
    arr = np.frombuffer(data, dtype=np.uint8).copy()
    return int(_compute_fingerprint_nb(arr))


def fingerprint_file(path: str) -> int:
    """
    파일 경로를 받아 fingerprint 계산.
    """
    with open(path, "rb") as f:
        data = f.read()
    return compute_fingerprint(data)


async def async_fingerprint_file(path: str) -> int:
    """
    파일 경로를 받아 비동기적으로 파일을 읽고 핑거프린트를 계산합니다.

    Args:
        path: 핑거프린트를 계산할 파일의 경로입니다.

    Returns:
        계산된 32비트 핑거프린트 정수입니다.

    Raises:
        FileNotFoundError: 파일이 존재하지 않는 경우.
        IOError: 파일 읽기 중 오류가 발생한 경우.
        Exception: 기타 예외.
    """
    try:
        async with aiofiles.open(path, "rb") as f:
            data = await f.read()
        return compute_fingerprint(data)
    except FileNotFoundError:
        print(f"오류: 파일을 찾을 수 없습니다 - {path}")
        raise
    except IOError as e:
        print(f"오류: 파일을 읽는 중 오류 발생 - {path}: {e}")
        raise
    except Exception as e:
        print(f"오류: 핑거프린트 계산 중 예상치 못한 오류 발생 - {path}: {e}")
        raise
