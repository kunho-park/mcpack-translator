import asyncio
import itertools
import json
import os
import time

from langchain_core.rate_limiters import InMemoryRateLimiter

from minecraft_modpack_auto_translator import translate_json_file
from minecraft_modpack_auto_translator.delay_manager import DelayManager
from minecraft_modpack_auto_translator.graph import create_translation_graph, registry
from minecraft_modpack_auto_translator.loaders.context import TranslationContext
from minecraft_modpack_auto_translator.parsers.base_parser import BaseParser
from minecraft_modpack_auto_translator.translator import get_translator

from .dictionary_builder import (
    DIR_FILTER_WHITELIST,
    build_dictionary_from_files,
    filter_korean_lang_files,
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
    force_keep_line_break=False,
):
    """여러 JSON 파일을 비동기 큐로 번역하고 결과 경로 목록을 반환합니다."""
    total = len(file_pairs)
    completed_count = 0
    provider = config["provider"]
    api_keys = config.get("api_keys", None)
    if api_keys is None or isinstance(api_keys, str):
        api_keys = ["sk-proj-1234567890"]
    api_base = config["api_base"]
    model_name = config["model_name"]
    temperature = config["temperature"]
    use_thinking_budget = config.get("use_thinking_budget", False)
    thinking_budget = config.get("thinking_budget", None)

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
        dict_init, dict_lower, count, added = build_dictionary_from_files(
            [fp["input"] for fp in file_pairs],
            os.getcwd(),
            dict_init,
            dict_lower,
            source_lang,
        )
        logger_client.write(
            f"기존 번역에서 추가된 사전 항목: {added}개 ({count}개의 파일에서)"
        )
    if custom_dictionary_path:
        dict_init, dict_lower = load_custom_dictionary(
            custom_dictionary_path, dict_init, dict_lower
        )
        logger_client.write("커스텀 사전 추가 완료")

    pre_len = len(file_pairs)
    file_pairs = filter_korean_lang_files(file_pairs, source_lang)
    logger_client.write(f"{pre_len - len(file_pairs)}개의 한글 번역 파일 건너뜀")
    # 워커들이 순환하며 사용할 API 키 이터레이터 생성
    key_cycle = itertools.cycle(api_keys)

    # LLM 인스턴스를 각 워커가 개별적으로 생성하도록 변경 (키 순환 사용)
    async def get_llm_instance_for_worker():
        selected_key = next(key_cycle)
        return get_translator(
            provider.lower(),
            selected_key,
            model_name,
            api_base,
            temperature,
            # --- RateLimiter 및 DelayManager 전달 --- #
            rate_limiter=rate_limiter,
            thinking_budget=thinking_budget if use_thinking_budget else None,
            # --- 전달 끝 --- #
        )

    # 사전 컨텍스트 초기화 (LLM 인스턴스 생성 전에 수행)
    context = TranslationContext(create_translation_graph(), dict_init, registry)
    context.initialize_dictionaries()

    results = []
    queue = asyncio.Queue()
    lock = asyncio.Lock()
    for pair in file_pairs:
        queue.put_nowait(pair)

    last_save_time = time.time()
    total_error_list = []

    async def process_file(pair):
        nonlocal last_save_time, total_error_list
        in_path = pair["input"]
        out_path = pair["output"]
        ko_data = pair["data"]

        if skip_translated and os.path.exists(out_path) and not any(
            d in out_path for d in DIR_FILTER_WHITELIST
        ):
            results.append(out_path)
            if logger_client:
                await logger_client.awrite(f"이미 번역된 파일 건너뛰기: {out_path}")
            return

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

        if logger_client:
            logger_client.write(f"번역 시작: {in_path}")

        error_list = await translate_json_file(
            input_path=temp_json_in,
            output_path=temp_json_out,
            ko_data=ko_data,
            custom_dictionary_dict=context.get_dictionary(),
            llm=llm_instance,
            max_workers=int(file_split_number),
            external_context=context,
            use_random_order=use_random_order,
            delay_manager=delay_manager,
            force_keep_line_break=force_keep_line_break,
        )
        total_error_list.extend(error_list)
        try:
            current_time = time.time()
            if current_time - last_save_time >= 300:  # 5분(300초)마다 저장
                os.makedirs("./temp/", exist_ok=True)
                path_for_shared_dict = os.path.join("./temp/last_shared_dict.json")
                with open(path_for_shared_dict, "w", encoding="utf-8") as jf:
                    json.dump(
                        context.get_dictionary(), jf, ensure_ascii=False, indent=4
                    )
                last_save_time = current_time  # 마지막 저장 시간 업데이트
        except Exception as e:
            if logger_client:
                logger_client.write(f"Error for save shared dict: {e}")
            return

        with open(temp_json_out, "r", encoding="utf-8") as f:
            data = json.load(f)
        if len(data) > 0:
            content = parser.save(data)
            # 최종 파일 저장
            with open(out_path, "w", encoding="utf-8") as of:
                of.write(content)

            results.append(out_path)
        if logger_client:
            logger_client.write(f"번역 완료: {out_path}")

    async def worker():
        nonlocal completed_count
        while not queue.empty():
            pair = await queue.get()

            try:
                await process_file(pair)
            except Exception as e:
                if logger_client:
                    logger_client.write(f"Error processing {pair}: {e}")
            finally:
                async with lock:
                    completed_count += 1
                    if progress_callback:
                        await progress_callback((completed_count, total))
                queue.task_done()

    if len(total_error_list) > 0:
        logger_client.write("\n\n" + "=" * 10)
        logger_client.write(f"번역 오류가 {len(total_error_list)}개 발생했습니다.")
        logger_client.write("오류 목록을 ./temp/error_list.json 에 저장했습니다.")
        logger_client.write("오류 목록을 확인하고 오류 수정 후 다시 번역해주세요.")
        with open("./temp/error_list.json", "w", encoding="utf-8") as f:
            json.dump(total_error_list, f, ensure_ascii=False, indent=4)
        logger_client.write("=" * 10 + "\n\n")

    # 워커 태스크 실행
    workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
    await queue.join()

    # 워커 태스크 취소
    for task in workers:
        task.cancel()

    # 취소된 태스크 처리 완료 대기
    await asyncio.gather(*workers, return_exceptions=True)
    return results, dict_init
