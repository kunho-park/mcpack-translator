import asyncio
import io
import os
import zipfile

from minecraft_modpack_auto_translator.resourcepack import create_resourcepack


async def package_categories(
    output_dir,
    categories_info,
    translate_config,
    translate_kubejs,
    translate_mods,
    resourcepack_name,
):
    """카테고리별 리소스팩을 비동기 큐로 생성합니다."""
    queue = asyncio.Queue()
    for category, info in categories_info.items():
        if (
            (category == "config" and not translate_config)
            or (category == "kubejs" and not translate_kubejs)
            or (category == "mods" and not translate_mods)
        ):
            continue
        queue.put_nowait((category, info))

    created_packs = []

    async def worker():
        while not queue.empty():
            category, info = await queue.get()
            pack_path = create_resourcepack(
                output_dir,
                [
                    os.path.join(output_dir, category, "output")
                    if category != "mods"
                    else os.path.join(output_dir, category, "extracted")
                ],
                resourcepack_name + info.get("suffix", ""),
            )
            created_packs.append(
                {
                    "category": category,
                    "info": info,
                    "path": pack_path,
                }
            )
            queue.task_done()

    # 워커 수는 큐 크기 또는 1 이상으로
    worker_count = max(queue.qsize(), 1)
    tasks = [asyncio.create_task(worker()) for _ in range(worker_count)]
    await queue.join()
    for t in tasks:
        t.cancel()
    return created_packs


def assemble_final_zip(
    created_packs,
    translation_dict_path,
    jar_files_fingerprint_path,
    failed_files_path,
    final_zip_name="results.zip",
):
    """생성된 리소스팩, 사전, Fingerprint, 실패 목록 파일을 ZIP으로 묶어 반환합니다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 리소스팩 추가
        for pack in created_packs:
            if os.path.exists(pack["path"]):
                zf.write(pack["path"], arcname=os.path.basename(pack["path"]))
        # 번역 사전 추가
        if translation_dict_path and os.path.exists(translation_dict_path):
            zf.write(
                translation_dict_path,
                arcname=os.path.join(
                    "dictionary", os.path.basename(translation_dict_path)
                ),
            )
        # Fingerprint 추가
        if jar_files_fingerprint_path and os.path.exists(jar_files_fingerprint_path):
            zf.write(
                jar_files_fingerprint_path,
                arcname=os.path.basename(jar_files_fingerprint_path),
            )
        # 실패 목록 추가
        if failed_files_path and os.path.exists(failed_files_path):
            zf.write(
                failed_files_path,
                arcname=os.path.basename(failed_files_path),
            )
    buf.seek(0)
    return buf.getvalue()
