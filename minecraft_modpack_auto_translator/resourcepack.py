import json
import logging
import os
import shutil
import zipfile
from glob import escape as glob_escape
from glob import glob

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("translation.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("resource_pack_creator")


def normalize_glob_path(path):
    """glob 패턴에서 사용할 경로를 정규화합니다."""
    normalized = path.replace("\\", "/")
    parts = []

    for part in normalized.split("/"):
        if part.startswith("**"):
            parts.append(part)
        elif part.startswith("*"):
            parts.append(part)
        else:
            parts.append(glob_escape(part))
    return "/".join(parts)


def create_resourcepack(
    output_dir,
    folder_list,
    pack_name="Korean-Translation",
    source_lang="en_us",
):
    """
    번역된 내용으로 마인크래프트 리소스팩을 생성합니다.

    Args:
        output_dir: 출력 디렉토리
        folder_list: 리소스팩에 포함할 폴더 및 파일 목록
        pack_name: 리소스팩 이름

    Returns:
        생성된 리소스팩 ZIP 파일 경로
    """
    # 리소스팩 디렉토리 생성 (임시 디렉토리)
    resourcepack_dir = os.path.join(output_dir, f"{pack_name}")

    # 기존 리소스팩 폴더가 있으면 삭제
    if os.path.exists(resourcepack_dir):
        shutil.rmtree(resourcepack_dir)

    # 리소스팩 기본 디렉토리 생성
    os.makedirs(resourcepack_dir, exist_ok=True)

    # pack.mcmeta 파일 생성
    pack_mcmeta = {
        "pack": {
            "pack_format": 15,  # Minecraft 1.20+ 버전용
            "description": f"{pack_name} - 한국어 번역 리소스팩",
        }
    }

    with open(
        os.path.join(resourcepack_dir, "pack.mcmeta"), "w", encoding="utf-8"
    ) as f:
        json.dump(pack_mcmeta, f, ensure_ascii=False, indent=4)

    # 아이콘 파일 복사 (있는 경우)
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pack.png")
    if os.path.exists(icon_path):
        shutil.copy(icon_path, os.path.join(resourcepack_dir, "pack.png"))

    # 번역 파일 처리
    for folder in folder_list:
        try:
            if not os.path.exists(folder):
                logger.warning(f"폴더 또는 파일이 존재하지 않습니다: {folder}")
                continue

            # 경로 정규화
            normalized_folder = os.path.normpath(folder)

            if "mods" in normalized_folder:
                extracted_glob_path = normalize_glob_path(
                    os.path.join(normalized_folder, "*")
                )
                for path in glob(extracted_glob_path, recursive=True):
                    if not os.path.exists(path):
                        continue

                    path_glob = normalize_glob_path(os.path.join(path, "**", "*"))
                    for src_file in glob(path_glob, recursive=True):
                        if os.path.isfile(src_file):
                            rel_path = os.path.relpath(src_file, path)
                            dst_file = os.path.join(resourcepack_dir, rel_path)

                            # 대상 디렉토리 존재 확인 후 생성
                            dst_dir = os.path.dirname(dst_file)
                            if not os.path.exists(dst_dir):
                                os.makedirs(dst_dir, exist_ok=True)

                            shutil.copy2(src_file, dst_file)

            elif (
                "kubejs" in normalized_folder
                or "config" in normalized_folder
                or "patchouli_books" in normalized_folder
            ):
                folder_glob_path = normalize_glob_path(
                    os.path.join(normalized_folder, "**", "*.*")
                )
                for path in glob(folder_glob_path, recursive=True):
                    if not os.path.exists(path):
                        continue

                    # 경로 정규화 및 상대 경로 계산
                    normalized_path = os.path.normpath(path).replace("\\", "/")
                    base_folder = os.path.normpath(normalized_folder).replace("\\", "/")
                    relative_path = (
                        normalized_path[len(base_folder) + 1 :]
                        if normalized_path.startswith(base_folder)
                        else normalized_path
                    )

                    to_copy_path = os.path.join(resourcepack_dir, relative_path)
                    dst_dir = os.path.dirname(to_copy_path)

                    if not os.path.exists(dst_dir):
                        os.makedirs(dst_dir, exist_ok=True)

                    if os.path.isfile(path):
                        shutil.copy(path, to_copy_path)
                    else:
                        shutil.copytree(path, to_copy_path)

        except Exception as e:
            logger.error(f"리소스팩 생성 중 오류 발생: {e}")

    # ZIP 파일로 압축 - 파일 구조 유지하면서 직접 생성
    zip_path = os.path.join(output_dir, f"{pack_name}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(resourcepack_dir):
            for file in files:
                # .tmp 파일 건너뛰기
                if (
                    file.endswith(".tmp")
                    or ".zip_extracted" in file
                    or file.endswith(".converted")
                ):
                    continue
                file_path = os.path.join(root, file)
                # 리소스팩 디렉토리를 기준으로 상대 경로 생성
                arcname = os.path.relpath(file_path, resourcepack_dir)
                arcname = arcname.replace(source_lang, "ko_kr").replace(
                    source_lang.split("_")[0] + "_" + source_lang.split("_")[1].upper(),
                    "ko_KR",
                )
                zipf.write(file_path, arcname)
                logger.debug(f"압축: {file_path} -> {arcname}")

    # 임시 디렉토리 정리
    shutil.rmtree(resourcepack_dir)

    logger.info(f"리소스팩 생성 완료: {zip_path}")
    return zip_path
