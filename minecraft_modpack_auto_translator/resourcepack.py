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


# 경로 특수 문자 처리 및 정규화
def normalize_glob_path(path):
    """
    glob 패턴에서 사용할 경로를 정규화합니다.
    경로 구분자를 통일하고 특수 문자가 있는 부분을 처리합니다.
    """
    # 경로 구분자 통일 (백슬래시 -> 슬래시)
    normalized_path = path.replace("\\", "/")

    # 와일드카드 있는지 확인
    has_wildcard = "*" in normalized_path or "?" in normalized_path

    if has_wildcard:
        # 경로와 패턴 부분 분리
        if "**" in normalized_path:
            # 재귀적 패턴 처리
            path_parts = normalized_path.split("/**", 1)
            base_dir = path_parts[0]
            pattern = "/**" + (path_parts[1] if len(path_parts) > 1 else "")
            # base_dir 부분만 이스케이프
            return glob_escape(base_dir) + pattern
        else:
            # 일반 와일드카드 패턴
            last_wildcard_idx = max(
                normalized_path.rfind("*"), normalized_path.rfind("?")
            )
            if last_wildcard_idx != -1:
                last_dir_sep = normalized_path.rfind("/", 0, last_wildcard_idx)
                if last_dir_sep != -1:
                    # 경로의 디렉토리 부분만 이스케이프
                    return (
                        glob_escape(normalized_path[:last_dir_sep])
                        + normalized_path[last_dir_sep:]
                    )

    # 와일드카드가 없으면 전체 경로 이스케이프
    return glob_escape(normalized_path)


def create_resourcepack(output_dir, folder_list, pack_name="Korean-Translation"):
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
        if not os.path.exists(folder):
            logger.warning(f"폴더 또는 파일이 존재하지 않습니다: {folder}")
            continue
        if "mods/" in folder:
            extracted_glob_path = normalize_glob_path(
                os.path.join(folder, "extracted", "*")
            )
            for path in glob(extracted_glob_path, recursive=True):
                # 모드 추출 파일을 리소스팩 디렉토리로 복사
                # 대상 디렉토리가 이미 존재하는 경우 오류가 발생할 수 있으므로
                # 파일별로 복사 진행
                # glob을 사용하여 모든 파일 찾기
                path_glob = normalize_glob_path(os.path.join(path, "**", "*"))
                for src_file in glob(path_glob, recursive=True):
                    if os.path.isfile(src_file):
                        # 원본 경로에서 상대 경로 추출
                        rel_path = os.path.relpath(src_file, path)
                        dst_file = os.path.join(resourcepack_dir, rel_path)

                        # 대상 디렉토리 생성
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)

                        # 파일 복사
                        shutil.copy2(src_file, dst_file)
        elif "kubejs" in folder or "config" in folder:
            folder_glob_path = normalize_glob_path(os.path.join(folder, "**", "*.*"))
            for path in glob(folder_glob_path, recursive=True):
                normalized_path = path.replace("\\", "/")
                normalized_folder = folder.replace("\\", "/")
                relative_path = "/".join(
                    normalized_path.split(normalized_folder)[1].split("/")[2:]
                )

                # 대상 경로 생성
                to_copy_path = os.path.join(resourcepack_dir, relative_path)
                os.makedirs(os.path.dirname(to_copy_path), exist_ok=True)
                if os.path.isfile(path):
                    shutil.copy(
                        path,
                        to_copy_path,
                    )
                else:
                    shutil.copytree(path, to_copy_path)

    # ZIP 파일로 압축 - 파일 구조 유지하면서 직접 생성
    zip_path = os.path.join(output_dir, f"{pack_name}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(resourcepack_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # 리소스팩 디렉토리를 기준으로 상대 경로 생성
                arcname = os.path.relpath(file_path, resourcepack_dir)
                zipf.write(file_path, arcname)
                logger.debug(f"압축: {file_path} -> {arcname}")

    # 임시 디렉토리 정리
    shutil.rmtree(resourcepack_dir)

    logger.info(f"리소스팩 생성 완료: {zip_path}")
    return zip_path
