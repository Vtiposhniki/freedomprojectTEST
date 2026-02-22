"""
Скачивает архив или папку с CSV файлами из Google Drive, распаковывает и загружает в БД.

Установка:
    pip install gdown python-magic-bin  (Windows)
    pip install gdown python-magic      (Linux/Mac)

Использование:
    python gdrive_loader.py --url "https://drive.google.com/file/d/.../view"
    python gdrive_loader.py --url "https://drive.google.com/drive/folders/..."

    или задай URL прямо в файле в переменной DEFAULT_URL ниже.
"""

import os
import logging
import zipfile
import tarfile
import hashlib
import argparse

import gdown

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

from db import get_connection, init_db, load_csv

# --------------------------------------------------
# Config
# --------------------------------------------------
DEFAULT_URL = "https://drive.google.com/file/d/1MYk9WK_0K_out54YaNUl41p2nzL24Ta8/view"

WORK_DIR    = "dataset"
ARCHIVE_DIR = os.path.join(WORK_DIR, "archives")
EXTRACT_DIR = os.path.join(WORK_DIR, "extracted")
LOG_FILE    = os.path.join(WORK_DIR, "process.log")

REMOVE_EXTENSIONS = [".txt", ".md", ".url", ".DS_Store"]

# Имена CSV файлов которые ищем после распаковки
CSV_NAMES = {
    "tickets":  ["tickets.csv"],
    "managers": ["managers.csv"],
    "units":    ["business_units.csv", "units.csv"],
}

# --------------------------------------------------
# Setup
# --------------------------------------------------
def setup():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
    logging.info("Process started")


# --------------------------------------------------
# URL helpers
# --------------------------------------------------
def is_folder_url(url: str) -> bool:
    """Определяет, является ли ссылка ссылкой на папку Google Drive."""
    return "/drive/folders/" in url or "?usp=sharing" in url and "/folders/" in url


# --------------------------------------------------
# Download
# --------------------------------------------------
def download_file(url: str) -> str:
    """Скачивает файл из Google Drive. Возвращает путь к скачанному файлу."""
    output = os.path.join(ARCHIVE_DIR, "archive")
    logging.info(f"Downloading file: {url}")
    path = gdown.download(url, output, fuzzy=True, quiet=False)
    if not path or not os.path.exists(path):
        raise Exception(
            "Файл не скачался. Проверь ссылку и доступ "
            "(Общий доступ -> Все у кого есть ссылка)"
        )
    logging.info(f"Downloaded to: {path}")
    return path


def download_folder(url: str) -> None:
    """Скачивает папку из Google Drive напрямую в EXTRACT_DIR."""
    logging.info(f"Downloading folder: {url}")
    gdown.download_folder(url, output=EXTRACT_DIR, quiet=False, use_cookies=False)
    logging.info(f"Folder downloaded to: {EXTRACT_DIR}")


# --------------------------------------------------
# Detect & Extract
# --------------------------------------------------
def detect_archive_type(path: str) -> str:
    """Определяет тип архива по сигнатуре файла."""

    # 1. Пробуем python-magic если доступен
    if MAGIC_AVAILABLE:
        try:
            mime = magic.from_file(path, mime=True)
            logging.info(f"MIME type: {mime}")
            if mime == "application/zip":
                return "zip"
            if mime in ("application/x-tar",):
                return "tar"
            if mime in ("application/gzip", "application/x-gzip"):
                return "tar.gz"
            if mime == "application/x-bzip2":
                return "tar.bz2"
            if mime == "application/x-xz":
                return "tar.xz"
        except Exception as e:
            logging.warning(f"MIME detection failed: {e}")

    # 2. Проверяем магические байты
    with open(path, "rb") as f:
        sig = f.read(8)

    if sig[:2] == b"PK":
        return "zip"
    if sig[:2] == b"\x1f\x8b":
        return "tar.gz"
    if sig[:3] == b"BZh":
        return "tar.bz2"
    if sig[:6] == b"\xfd7zXZ\x00":
        return "tar.xz"

    # 3. Пробуем tarfile как fallback (он сам умеет определять формат)
    if tarfile.is_tarfile(path):
        return "tar"

    # 4. Последняя попытка — zipfile
    if zipfile.is_zipfile(path):
        return "zip"

    # Диагностика: покажем первые байты чтобы понять что пришло
    with open(path, "rb") as f:
        header = f.read(64)
    logging.error(f"Unknown format. First bytes: {header!r}")
    print(f"  ⚠ Первые байты файла: {header!r}")

    # Если это HTML — скорее всего пришла страница подтверждения Drive
    if b"<!DOCTYPE" in header or b"<html" in header.lower():
        raise Exception(
            "Google Drive вернул HTML страницу вместо файла.\n"
            "Возможные причины:\n"
            "  1. Файл не открыт для общего доступа\n"
            "  2. Файл слишком большой — Drive требует подтверждения\n"
            "  3. Неверная ссылка\n"
            "Попробуй: gdown --fuzzy '<url>' или проверь настройки доступа."
        )

    raise Exception(f"Неподдерживаемый формат архива. Первые байты: {header!r}")


def safe_extract_zip(path: str):
    """Безопасная распаковка ZIP с защитой от Zip Slip."""
    real_extract = os.path.realpath(EXTRACT_DIR)
    with zipfile.ZipFile(path) as z:
        for member in z.infolist():
            extracted_path = os.path.realpath(os.path.join(EXTRACT_DIR, member.filename))
            if not extracted_path.startswith(real_extract + os.sep) and extracted_path != real_extract:
                raise Exception(f"Zip Slip detected: {member.filename}")
        z.extractall(EXTRACT_DIR)


def safe_extract_tar(path: str, mode: str = "r:*"):
    """Безопасная распаковка TAR с защитой от Path Traversal.
    mode='r:*' позволяет tarfile самому определить сжатие (gz, bz2, xz, plain).
    """
    real_extract = os.path.realpath(EXTRACT_DIR)
    with tarfile.open(path, mode) as tar:
        for member in tar.getmembers():
            member_path = os.path.realpath(os.path.join(EXTRACT_DIR, member.name))
            if not member_path.startswith(real_extract + os.sep) and member_path != real_extract:
                raise Exception(f"Tar Path Traversal detected: {member.name}")
        tar.extractall(EXTRACT_DIR)


def extract_archive(path: str):
    """Определяет тип архива и распаковывает его."""
    size = os.path.getsize(path)
    logging.info(f"Archive size: {size} bytes")
    print(f"  Размер файла: {size:,} байт")

    t = detect_archive_type(path)
    logging.info(f"Archive type: {t}")
    print(f"  Тип архива: {t}")

    if t == "zip":
        safe_extract_zip(path)
    elif t in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
        # mode="r:*" — tarfile сам разберётся со сжатием
        safe_extract_tar(path, mode="r:*")
    else:
        raise Exception(f"Неподдерживаемый формат: {t}")

    logging.info("Extraction finished")
    print("  Распаковка завершена.")


# --------------------------------------------------
# Cleanup
# --------------------------------------------------
def cleanup_files():
    removed = 0
    for root, dirs, files in os.walk(EXTRACT_DIR):
        for file in files:
            path = os.path.join(root, file)
            if any(file.endswith(ext) for ext in REMOVE_EXTENSIONS):
                os.remove(path)
                logging.info(f"Removed: {path}")
                removed += 1
    logging.info(f"Cleanup: removed {removed} files")
    print(f"  Удалено лишних файлов: {removed}")


# --------------------------------------------------
# Find CSVs
# --------------------------------------------------
def find_csv(key: str) -> str:
    candidates = [c.lower() for c in CSV_NAMES[key]]
    for root, dirs, files in os.walk(EXTRACT_DIR):
        for f in files:
            if f.lower() in candidates:
                found = os.path.join(root, f)
                logging.info(f"Found {key}: {found}")
                return found

    # Показываем что реально есть в архиве
    found_files = []
    for root, dirs, files in os.walk(EXTRACT_DIR):
        for f in files:
            found_files.append(os.path.relpath(os.path.join(root, f), EXTRACT_DIR))

    raise FileNotFoundError(
        f"Не найден файл для '{key}'. Ожидались: {CSV_NAMES[key]}\n"
        f"Файлы в архиве: {found_files}"
    )


# --------------------------------------------------
# DB helpers
# --------------------------------------------------
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def clear_all():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE assignments  RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE ai_analysis  RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE tickets      RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE managers     RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE offices      RESTART IDENTITY CASCADE;")
        conn.commit()
        print("[DB] Таблицы очищены")
        logging.info("DB cleared")
    finally:
        conn.close()


# --------------------------------------------------
# Main
# --------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url", default=DEFAULT_URL,
        help="Ссылка на архив или папку в Google Drive"
    )
    args = parser.parse_args()

    url = args.url or DEFAULT_URL
    if not url:
        print("Укажи ссылку: python gdrive_loader.py --url 'https://drive.google.com/...'")
        return

    setup()

    folder_mode = is_folder_url(url)

    if folder_mode:
        # ---- Режим папки: скачиваем файлы напрямую в EXTRACT_DIR ----
        print("\n1. Скачиваем папку из Google Drive...")
        download_folder(url)
        print("\n2. Очищаем лишние файлы...")
        cleanup_files()
    else:
        # ---- Режим файла: скачиваем архив и распаковываем ----
        print("\n1. Скачиваем архив...")
        archive = download_file(url)
        checksum = sha256(archive)
        print(f"   SHA256: {checksum}")
        logging.info(f"SHA256: {checksum}")

        print("\n2. Распаковываем...")
        extract_archive(archive)

        print("\n3. Очищаем лишние файлы...")
        cleanup_files()

    print("\n4. Ищем CSV файлы...")  # номер шага одинаковый в обоих режимах
    tickets_path  = find_csv("tickets")
    managers_path = find_csv("managers")
    units_path    = find_csv("units")
    print(f"   tickets:  {tickets_path}")
    print(f"   managers: {managers_path}")
    print(f"   units:    {units_path}")

    print("\n5. Очищаем БД и загружаем...")
    init_db()
    clear_all()
    load_csv(
        tickets_path  = tickets_path,
        managers_path = managers_path,
        units_path    = units_path,
    )

    logging.info("Process completed")
    print("\n✓ Готово! Теперь запусти:")
    print("  python run.py")
    print("  python analyze.py")


if __name__ == "__main__":
    main()