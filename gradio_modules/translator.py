import asyncio
import itertools
import json
import os

from langchain_core.rate_limiters import InMemoryRateLimiter

from minecraft_modpack_auto_translator import translate_json_file
from minecraft_modpack_auto_translator.delay_manager import DelayManager
from minecraft_modpack_auto_translator.graph import create_translation_graph, registry
from minecraft_modpack_auto_translator.loaders.context import TranslationContext
from minecraft_modpack_auto_translator.parsers.base_parser import BaseParser
from minecraft_modpack_auto_translator.translator import get_translator

from .dictionary_builder import (
    build_dictionary_from_files,
    initialize_translation_dictionary,
    load_custom_dictionary,
)


async def run_json_translation(
    file_pairs,
    source_lang,
    config,
    build_dict,
    skip_translated,
    max_workers,
    file_split_number,
    use_random_order,
    custom_dictionary_path=None,
    progress_callback=None,
    logger_client=None,
):
    """여러 JSON 파일을 비동기 큐로 번역하고 결과 경로 목록을 반환합니다."""
    total = len(file_pairs)
    completed_count = 0
    lock = asyncio.Lock()
    provider = config["provider"]
    api_keys = config.get("api_keys", [])
    if not api_keys:
        if logger_client:
            logger_client.write("오류: 설정된 API 키가 없습니다.")
        raise ValueError("API 키가 설정되지 않았습니다.")
    api_base = config["api_base"]
    model_name = config["model_name"]
    temperature = config["temperature"]

    # --- 속도 제한 및 지연 설정 로드 --- #
    use_rate_limiter = config.get("use_rate_limiter", False)
    rpm = config.get("rpm", 60)
    use_request_delay = config.get("use_request_delay", False)
    request_delay = config.get("request_delay", 1.0)

    # Convert RPM to requests per second for InMemoryRateLimiter
    requests_per_second = rpm / 60.0
    rate_limiter = (
        InMemoryRateLimiter(requests_per_second=requests_per_second)
        if use_rate_limiter
        else None
    )
    delay_manager = DelayManager(request_delay) if use_request_delay else None

    if rate_limiter and logger_client:
        logger_client.write(
            f"속도 제한 활성화: {requests_per_second:.2f} RPS ({rpm} RPM)"
        )
    if delay_manager and logger_client:
        logger_client.write(f"요청 지연 활성화: {request_delay}초")
    # --- 설정 로드 끝 --- #

    # 사전 초기화
    dict_init, dict_lower = initialize_translation_dictionary(
        source_lang, os.getenv("LANG_CODE", "ko_kr")
    )
    if build_dict:
        dict_init, dict_lower, added, _ = build_dictionary_from_files(
            [fp["input"] for fp in file_pairs],
            os.getcwd(),
            dict_init,
            dict_lower,
            source_lang,
        )
        logger_client.write(f"기존 번역에서 추가된 사전 항목: {added}개")

    if custom_dictionary_path:
        dict_init, dict_lower = load_custom_dictionary(
            custom_dictionary_path, dict_init, dict_lower
        )
        logger_client.write("커스텀 사전 추가 완료")

    # 워커들이 순환하며 사용할 API 키 이터레이터 생성
    key_cycle = itertools.cycle(api_keys)

    # LLM 인스턴스를 각 워커가 개별적으로 생성하도록 변경 (키 순환 사용)
    async def get_llm_instance_for_worker():
        async with lock:  # Lock을 사용하여 순차적으로 키를 가져옴
            selected_key = next(key_cycle)
        return get_translator(
            provider.lower(),
            selected_key,
            model_name,
            api_base,
            temperature,
            # --- RateLimiter 및 DelayManager 전달 --- #
            rate_limiter=rate_limiter,
            # --- 전달 끝 --- #
        )

    # 사전 컨텍스트 초기화 (LLM 인스턴스 생성 전에 수행)
    context = TranslationContext(create_translation_graph(), dict_init, registry)
    context.initialize_dictionaries()

    results = []
    queue = asyncio.Queue()
    for pair in file_pairs:
        queue.put_nowait(pair)

    async def worker():
        nonlocal completed_count
        while not queue.empty():
            try:
                pair = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                in_path = pair["input"]
                out_path = pair["output"]
                # 이미 번역된 파일 건너뛰기
                if skip_translated and os.path.exists(out_path):
                    results.append(out_path)
                    if logger_client:
                        logger_client.write(f"이미 번역된 파일 건너뛰기: {out_path}")
                    continue
                # 임시 JSON 파일로 번역
                temp_json_out = out_path + ".tmp"
                temp_json_in = in_path + ".converted"
                llm_instance = await get_llm_instance_for_worker()

                ext = os.path.splitext(in_path)[1]
                parser = BaseParser.get_parser_by_extension(ext)
                with open(in_path, "rb") as f:
                    content_bytes = f.read()
                try:
                    content_str = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    content_str = content_bytes.decode("utf-8", errors="ignore")
                original_data = parser.load(content_str)
                json_input = json.dumps(original_data, ensure_ascii=False, indent=4)

                with open(temp_json_in, "w", encoding="utf-8") as of:
                    of.write(json_input)

                with lock:
                    if logger_client:
                        logger_client.write(f"번역 시작: {in_path}")
                    completed_count += 1
                    await progress_callback((completed_count, total))

                await translate_json_file(
                    input_path=temp_json_in,
                    output_path=temp_json_out,
                    custom_dictionary_dict=context.get_dictionary(),
                    llm=llm_instance,
                    max_workers=int(file_split_number),
                    external_context=context,
                    use_random_order=use_random_order,
                    delay_manager=delay_manager,
                )
                # 변환: JSON -> 원본 포맷
                with open(temp_json_out, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                # 파서로 저장
                content = parser.save(data)
                # 최종 파일 저장
                with open(out_path, "w", encoding="utf-8") as of:
                    of.write(content)

                results.append(out_path)
                with lock:
                    if logger_client:
                        logger_client.write(f"번역 완료: {out_path}")
                    # 파일 번역 완료 시 진행률 업데이트
            except Exception as e:
                # 예외 로깅 또는 처리 (선택 사항)
                with lock:
                    if logger_client:
                        logger_client.write(f"Error processing {pair}: {e}")
                # 필요한 경우 추가적인 오류 처리 로직 추가
            finally:
                # 예외 발생 여부와 관계없이 항상 task_done() 호출
                async with lock:
                    completed_count += 1
                    if progress_callback:
                        await progress_callback((completed_count, total))
                queue.task_done()

    # 워커 태스크 실행
    workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
    await queue.join()

    # 워커 태스크 취소
    for task in workers:
        task.cancel()

    # 취소된 태스크 처리 완료 대기
    await asyncio.gather(*workers, return_exceptions=True)
    return results, dict_init
