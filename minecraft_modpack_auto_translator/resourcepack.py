import json
import logging
import os
import shutil
import tempfile
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


def repack_mods(mods_folder):
    """
    mods 폴더 내의 input 및 output 폴더를 기반으로 .jar 파일을 리패키징합니다.

    1. output 폴더 내에 'data' 디렉토리가 있는 폴더를 찾습니다.
    2. 해당 input 폴더 내용으로 임시 zip 파일을 생성합니다.
    3. output 폴더 내용으로 임시 zip 파일을 업데이트(덮어쓰기)합니다.
    4. 최종 .jar 파일을 mods_folder에 저장합니다.

    Args:
        mods_folder: input 및 output 폴더가 포함된 상위 폴더 경로

    Returns:
        생성된 .jar 파일 경로 리스트
    """
    created_jars = []

    jars_folder = os.path.join("./temp", "jars")
    os.makedirs(jars_folder, exist_ok=True)

    for item_path in glob(os.path.join(mods_folder, "*")):
        if not os.path.isdir(item_path):
            continue  # 폴더만 처리

        output_folder = item_path
        # output 폴더 이름으로 input 폴더 경로를 구성합니다.
        folder_name = os.path.basename(output_folder)

        # input_folder = output_folder.replace("output", "input") # 이전 방식
        input_jar_filename = folder_name  # .jar 확장자 추가
        input_jar_path = (
            mods_folder.replace("output", "input").replace("mods/extracted", "mods")
            + "/"
            + input_jar_filename
        )

        # output 폴더 내에 'data' 디렉토리가 있는지 확인합니다.
        try:
            if "data" in os.listdir(output_folder):
                logger.info(f"Processing folder: {folder_name}")

                # input JAR 파일 존재 여부 확인
                input_jar_exists = os.path.isfile(input_jar_path)
                if not input_jar_exists:
                    logger.warning(
                        f"Input JAR file not found at {input_jar_path}, skipping initial packing from JAR."
                    )
                # else: # input_folder_exists 불필요, input_jar_exists로 대체
                #     input_folder_exists = True

                # 임시 zip 파일 생성
                temp_zip_file = None  # finally 블록에서 사용하기 위해 초기화
                temp_zip_path_for_finally = None  # finally에서 사용할 임시 zip 경로
                try:
                    # 임시 파일 생성 (고유 이름 보장)
                    temp_fd, temp_zip_path = tempfile.mkstemp(suffix=".temp_zip")
                    temp_zip_path_for_finally = (
                        temp_zip_path  # finally에서 참조할 수 있도록 할당
                    )
                    os.close(temp_fd)  # 핸들 닫기
                    temp_zip_file = zipfile.ZipFile(
                        temp_zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
                    )
                    logger.debug(f"Created temporary zip file: {temp_zip_path}")
                    # added_arcnames = set() # Output 우선 로직에서 사용, 현재는 불필요

                    added = []
                    logger.info(
                        f"Packing/overwriting contents from output: {output_folder}"
                    )
                    for root, _, files in os.walk(output_folder):
                        for file in files:
                            if (
                                file.endswith(
                                    ".temp_zip"
                                )  # 생성 중인 임시 zip 파일 자체는 추가하지 않음
                                or file.endswith(".tmp")
                                or ".zip_extracted" in file
                                or file.endswith(".converted")
                            ):
                                continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, output_folder)
                            temp_zip_file.write(file_path, arcname)
                            logger.debug(f"Added/overwritten from output: {arcname}")
                            added.append(arcname)

                    # 1. input JAR 내용 압축 (존재하는 경우)
                    if input_jar_exists:
                        logger.info(
                            f"Packing contents from input JAR: {input_jar_path}"
                        )
                        with zipfile.ZipFile(input_jar_path, "r") as src_jar:
                            for member_info in src_jar.infolist():
                                # 특정 임시 파일 등 건너뛰기
                                if member_info.filename in added:
                                    continue
                                member_data = src_jar.read(member_info.filename)
                                temp_zip_file.writestr(member_info, member_data)
                                logger.debug(
                                    f"Added from input JAR: {member_info.filename}"
                                )

                    temp_zip_file.close()  # 파일 쓰기 완료 후 닫기
                    temp_zip_file = None  # 정상 종료 시 None으로 설정하여 finally에서 중복 close 방지

                    # 3. 최종 .jar 파일 생성 및 이동
                    final_jar_name = f"{folder_name}{'.jar' if not folder_name.endswith('.jar') else ''}"
                    final_jar_path = os.path.join(jars_folder, final_jar_name)

                    # 기존 파일이 있으면 덮어쓰기 (shutil.move가 이를 처리)
                    shutil.move(temp_zip_path, final_jar_path)
                    temp_zip_path_for_finally = None  # 이동 성공 시 삭제 대상에서 제외
                    logger.info(f"Successfully created JAR: {final_jar_path}")
                    created_jars.append(final_jar_path)
                    # temp_zip_file = None  # 이미 위에서 None으로 설정됨

                except Exception as e:
                    logger.error(
                        f"Error processing folder {folder_name}: {e}", exc_info=True
                    )
                finally:
                    # 임시 파일 정리 (오류 발생 또는 정상 처리 완료 후)
                    if temp_zip_file:  # 파일 객체가 아직 열려있다면 닫기 (예외 발생 시)
                        try:
                            temp_zip_file.close()
                        except Exception as close_err:
                            logger.error(
                                f"Error closing temporary zip file during finally: {close_err}"
                            )
                    if temp_zip_path_for_finally and os.path.exists(
                        temp_zip_path_for_finally
                    ):  # 임시 파일 경로가 존재하고 파일이 남아있다면 삭제
                        try:
                            os.remove(temp_zip_path_for_finally)
                            logger.debug(
                                f"Removed temporary zip file: {temp_zip_path_for_finally}"
                            )
                        except Exception as remove_err:
                            logger.error(
                                f"Error removing temporary zip file {temp_zip_path_for_finally}: {remove_err}"
                            )

            else:
                logger.debug(
                    f"'data' directory not found in {output_folder}, skipping."
                )
        except FileNotFoundError:
            logger.warning(f"Could not list directory, skipping: {output_folder}")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while processing {output_folder}: {e}",
                exc_info=True,
            )

    return created_jars


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
