import json
import logging
import os
import traceback
import zipfile
from glob import escape as glob_escape
from glob import glob

from gradio_modules.utils import extract_lang_content
from minecraft_modpack_auto_translator.config import (
    DICTIONARY_PREFIX_WHITELIST,
    DICTIONARY_SUFFIX_BLACKLIST,
    DIR_FILTER_WHITELIST,
    OFFICIAL_EN_LANG_FILE,
    OFFICIAL_KO_LANG_FILE,
)
from minecraft_modpack_auto_translator.finger_print import fingerprint_file
from minecraft_modpack_auto_translator.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


def add_to_dictionary(
    en_value, ko_value, translation_dictionary, translation_dictionary_lowercase
):
    """번역 사전에 항목 추가 (중복 처리 포함)"""
    try:
        key_lower = en_value.lower()
        if key_lower in translation_dictionary_lowercase:
            orig_key = translation_dictionary_lowercase[key_lower]
            target = translation_dictionary[orig_key]
            if isinstance(target, list):
                if ko_value not in target:
                    target.append(ko_value)
            elif isinstance(target, str):
                if target != ko_value:
                    translation_dictionary[orig_key] = [target, ko_value]
        else:
            translation_dictionary[en_value] = ko_value
            translation_dictionary_lowercase[key_lower] = en_value
    except Exception:
        traceback.print_exc()
    return translation_dictionary, translation_dictionary_lowercase


def initialize_translation_dictionary(source_lang_code, target_lang_code):
    """공식 번역 및 커스텀 사전으로 번역 사전을 초기화합니다."""
    translation_dictionary = {}
    translation_dictionary_lowercase = {}
    # 공식 마인크래프트 번역 파일에서 사전 구축 (en_us -> ko_kr)
    if source_lang_code == "en_us" and target_lang_code == "ko_kr":
        for key, en_val in OFFICIAL_EN_LANG_FILE.items():
            if key in OFFICIAL_KO_LANG_FILE:
                ko_val = OFFICIAL_KO_LANG_FILE[key]
                if en_val and ko_val:
                    add_to_dictionary(
                        en_val,
                        ko_val,
                        translation_dictionary,
                        translation_dictionary_lowercase,
                    )
    return translation_dictionary, translation_dictionary_lowercase


def load_custom_dictionary(
    custom_dict_file, translation_dictionary, translation_dictionary_lowercase
):
    """업로드된 커스텀 사전 파일을 로드하고 기존 사전에 병합합니다."""
    if custom_dict_file is not None:
        with open(custom_dict_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for en, ko in data.items():
            if isinstance(ko, list):
                for k in ko:
                    add_to_dictionary(
                        en, k, translation_dictionary, translation_dictionary_lowercase
                    )
            else:
                add_to_dictionary(
                    en, ko, translation_dictionary, translation_dictionary_lowercase
                )
    return translation_dictionary, translation_dictionary_lowercase


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


def process_modpack_directory(
    modpack_path,
    source_lang_code,
    translate_config=True,
    translate_kubejs=True,
    translate_mods=True,
):
    """모드팩 디렉토리에서 번역 대상 파일을 찾습니다."""
    from gradio_modules.utils import get_supported_extensions

    try:
        extact_all_zip_files(modpack_path)
    except Exception:
        logger.error(f"데이터팩, 리소스팩 zip 파일 추출 실패: {modpack_path}")

    supported_exts = get_supported_extensions()
    src_lower = source_lang_code.lower()
    files = []
    # config
    if translate_config:
        cfg_pattern = normalize_glob_path(os.path.join(modpack_path, "config/**/*.*"))
        for f in glob(cfg_pattern, recursive=True):
            f = f.replace("\\", "/")
            ext = os.path.splitext(f)[1]
            if ext in supported_exts and any(d in f for d in DIR_FILTER_WHITELIST):
                if "lang/" in f:
                    if ext in supported_exts and src_lower in f.lower():
                        files.append(f)
                else:
                    files.append(f)
            elif ext in supported_exts and src_lower in f.lower():
                files.append(f)

    logger.info(f"찾은 파일: {len(files)}개 (config 처리)")
    # kubejs
    if translate_kubejs:
        kjs_pattern = normalize_glob_path(os.path.join(modpack_path, "kubejs/**/*.*"))
        for f in glob(kjs_pattern, recursive=True):
            f = f.replace("\\", "/")
            ext = os.path.splitext(f)[1]
            if ext in supported_exts and any(d in f for d in DIR_FILTER_WHITELIST):
                if "lang/" in f:
                    if ext in supported_exts and src_lower in f.lower():
                        files.append(f)
                else:
                    files.append(f)
            elif ext in supported_exts and src_lower in f.lower():
                files.append(f)

    logger.info(f"찾은 파일: {len(files)}개 (kubejs 처리)")
    # mods
    jar_files = []
    fingerprints = {}
    if translate_mods:
        jar_pattern = normalize_glob_path(os.path.join(modpack_path, "mods/*.jar"))
        for jar in glob(jar_pattern):
            fingerprints[os.path.basename(jar)] = fingerprint_file(jar)
            with zipfile.ZipFile(jar, "r") as zf:
                logger.info(f"Jar 압축 해제중: {jar}")
                out_dir = os.path.join(
                    modpack_path,
                    "mods",
                    "extracted",
                    os.path.basename(jar),
                )
                os.makedirs(out_dir, exist_ok=True)
                for entry in zf.namelist():
                    if os.path.splitext(entry)[1].lower() in (
                        ".sbnt",
                        ".txt",
                        ".json",
                        ".zip",
                        ".lang",
                        ".md",
                    ):
                        try:
                            zf.extract(entry, out_dir)
                        except Exception:
                            logger.error(f"JAR 파일에서 추출 실패: {entry} ({jar})")
                for entry in zf.namelist():
                    if os.path.splitext(entry)[1] in supported_exts and (
                        any(d in entry for d in DIR_FILTER_WHITELIST)
                        or src_lower in entry.lower()
                    ):
                        files.append(os.path.join(out_dir, entry))
            jar_files.append(jar)

    logger.info(f"찾은 파일: {len(files)}개 (mods 처리)")
    return files, jar_files, fingerprints


def build_dictionary_from_jar(
    jar_files,
    translation_dictionary,
    translation_dictionary_lowercase,
    source_lang_code,
):
    """JAR 파일 내부의 언어 파일에서 번역 사전을 구축합니다."""

    count, added = 0, 0
    for jar in jar_files:
        with zipfile.ZipFile(jar, "r") as zf:
            for f in zf.namelist():
                if source_lang_code.lower() in f.lower():
                    target = f.replace(source_lang_code, "ko_kr").replace(
                        source_lang_code.split("_")[0]
                        + "_"
                        + source_lang_code.split("_")[1].upper(),
                        "ko_KR",
                    )
                    if target in zf.namelist():
                        en_c = zf.read(f).decode("utf-8", errors="ignore")
                        ko_c = zf.read(target).decode("utf-8", errors="ignore")
                        parser = BaseParser.get_parser_by_extension(
                            os.path.splitext(f)[1]
                        )
                        en_data = parser.load(en_c)
                        ko_data = parser.load(ko_c)
                        for k, v in en_data.items():
                            if (
                                k in ko_data
                                and isinstance(v, str)
                                and isinstance(ko_data[k], str)
                            ):
                                clean_e = v.replace("_", "")
                                clean_k = ko_data[k].replace("_", "")
                                (
                                    translation_dictionary,
                                    translation_dictionary_lowercase,
                                ) = add_to_dictionary(
                                    clean_e,
                                    clean_k,
                                    translation_dictionary,
                                    translation_dictionary_lowercase,
                                )
                                added += 1
                        count += 1
    return translation_dictionary, translation_dictionary_lowercase, count, added


def build_dictionary_from_files(
    en_us_files,
    modpack_path,
    translation_dictionary,
    translation_dictionary_lowercase,
    source_lang_code,
):
    """파일 시스템 내 언어 파일에서 번역 사전을 구축합니다."""
    count, added = 0, 0
    for en_file in en_us_files:
        rel = en_file
        target = rel.replace(
            source_lang_code,
            "ko_kr",
        ).replace(
            source_lang_code.split("_")[0]
            + "_"
            + source_lang_code.split("_")[1].upper(),
            "ko_KR",
        )
        if "Ponder-Forge-1.20.1-1.0.0.jar" in en_file:
            print(target)

        if os.path.exists(target) and target != en_file:
            try:
                en_data = extract_lang_content(en_file)
                ko_data = extract_lang_content(target)
                if isinstance(en_data, dict) and isinstance(ko_data, dict):
                    for key, ev in en_data.items():
                        if (
                            key in ko_data
                            and isinstance(ev, str)
                            and isinstance(ko_data[key], str)
                        ):
                            if ev == ko_data[key]:
                                continue
                            if (
                                key.split(".")[0] in DICTIONARY_PREFIX_WHITELIST
                                and key.split(".")[-1]
                                not in DICTIONARY_SUFFIX_BLACKLIST
                            ):
                                clean_e = ev.replace("_", "")
                                clean_k = ko_data[key].replace("_", "")
                                (
                                    translation_dictionary,
                                    translation_dictionary_lowercase,
                                ) = add_to_dictionary(
                                    clean_e,
                                    clean_k,
                                    translation_dictionary,
                                    translation_dictionary_lowercase,
                                )
                                added += 1
                    count += 1
            except Exception:
                logger.error(f"기존 번역에서 파일 읽기 실패: {en_file}")
    return translation_dictionary, translation_dictionary_lowercase, count, added


def filter_korean_lang_files(files, source_lang_code):
    """한글 번역 파일을 필터링합니다."""
    filtered_files = []

    for f in files:
        ko_path = (
            f["input"]
            .replace(source_lang_code, "ko_kr")
            .replace(
                source_lang_code.split("_")[0]
                + "_"
                + source_lang_code.split("_")[1].upper(),
                "ko_KR",
            )
        )
        added = False
        if os.path.exists(ko_path) or any(
            d in f["input"] for d in DIR_FILTER_WHITELIST
        ):
            if ko_path != f["input"]:
                with open(ko_path, "r", encoding="utf-8") as file:
                    parser = BaseParser.get_parser_by_extension(
                        os.path.splitext(f["input"])[1]
                    )
                    try:
                        ko_data = parser.load(file.read())
                    except Exception:
                        ko_data = {}
                    if ko_data:
                        added = True
                        filtered_files.append(
                            {
                                "input": f["input"],
                                "output": f["output"],
                                "data": ko_data,
                            }
                        )
        if not added:
            filtered_files.append(
                {
                    "input": f["input"],
                    "output": f["output"],
                    "data": {},
                }
            )
    return filtered_files


def extact_all_zip_files(modpack_path):
    zip_files = glob(
        normalize_glob_path(os.path.join(modpack_path, "**", "*.zip")), recursive=True
    )
    for zip_file in zip_files:
        with zipfile.ZipFile(zip_file, "r") as zf:
            if "datapacks" in zip_file or "resourcepacks" in zip_file:
                zip_file_edited = zip_file.replace("\\", "/") + ".zip_extracted"
                if os.path.exists(zip_file_edited):
                    logger.info(f"이미 추출된 파일: {zip_file}")
                    continue

                os.makedirs(zip_file_edited, exist_ok=True)
                try:
                    zf.extractall(zip_file_edited)
                except Exception:
                    logger.error(f"zip 파일 추출 실패: {zip_file}")
    return zip_files


def restore_zip_files(modpack_path, source_lang="en_us"):
    """.zip_extracted 폴더들을 찾아 원본 zip 파일로 복구합니다."""
    extracted_dirs = glob(
        normalize_glob_path(os.path.join(modpack_path, "**", "*.zip_extracted")),
        recursive=True,
    )
    for extracted_dir in extracted_dirs:
        zip_path = extracted_dir.replace(".zip_extracted", "")  # .zip_extracted 제거
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(extracted_dir):
                for file in files:
                    if (
                        file.endswith(".tmp")
                        or ".zip_extracted" in file
                        or file.endswith(".converted")
                    ):
                        continue
                    file_path = os.path.join(root, file)
                    arcname = (
                        os.path.relpath(file_path, extracted_dir)
                        .replace(source_lang, "ko_kr")
                        .replace(
                            source_lang.split("_")[0]
                            + "_"
                            + source_lang.split("_")[1].upper(),
                            "ko_KR",
                        )
                    )
                    zf.write(file_path, arcname)
    return extracted_dirs
