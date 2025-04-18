import json
import os
import shutil
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
        data = json.load(custom_dict_file)
        for en, ko in data.items():
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
                files.append(f)
            elif ext in supported_exts and src_lower in f.lower():
                files.append(f)
    # kubejs
    if translate_kubejs:
        kjs_pattern = normalize_glob_path(os.path.join(modpack_path, "kubejs/**/*.*"))
        for f in glob(kjs_pattern, recursive=True):
            f = f.replace("\\", "/")
            ext = os.path.splitext(f)[1]
            if ext in supported_exts and any(d in f for d in DIR_FILTER_WHITELIST):
                files.append(f)
            elif ext in supported_exts and src_lower in f.lower():
                files.append(f)
    # mods
    jar_files = []
    fingerprints = {}
    if translate_mods:
        jar_pattern = normalize_glob_path(os.path.join(modpack_path, "mods/*.jar"))
        for jar in glob(jar_pattern):
            fingerprints[os.path.basename(jar)] = fingerprint_file(jar)
            with zipfile.ZipFile(jar, "r") as zf:
                for entry in zf.namelist():
                    if os.path.splitext(entry)[1] in supported_exts and (
                        any(d in entry for d in DIR_FILTER_WHITELIST)
                        or src_lower in entry.lower()
                    ):
                        out = os.path.join(
                            modpack_path,
                            "mods",
                            "extracted",
                            os.path.basename(jar),
                            entry,
                        )
                        os.makedirs(os.path.dirname(out), exist_ok=True)
                        with zf.open(entry) as src, open(out, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        files.append(out)
            jar_files.append(jar)
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
                    target = f.replace(
                        source_lang_code, os.getenv("LANG_CODE", "ko_kr"), 1
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
        rel = en_file.replace(modpack_path, "").lstrip("/\\")
        target = os.path.join(
            modpack_path,
            rel.replace(source_lang_code, os.getenv("LANG_CODE", "ko_kr"), 1),
        )
        if os.path.exists(target):
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
                            and key.split(".")[-1] not in DICTIONARY_SUFFIX_BLACKLIST
                        ):
                            clean_e = ev.replace("_", "")
                            clean_k = ko_data[key].replace("_", "")
                            translation_dictionary, translation_dictionary_lowercase = (
                                add_to_dictionary(
                                    clean_e,
                                    clean_k,
                                    translation_dictionary,
                                    translation_dictionary_lowercase,
                                )
                            )
                            added += 1
                count += 1
    return translation_dictionary, translation_dictionary_lowercase, count, added
