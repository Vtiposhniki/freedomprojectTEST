# gdrive_loader.py
"""
Скачивает архив с CSV файлами из Google Drive, распаковывает и загружает в БД.

Установка:
    pip install gdown python-magic-bin  (Windows)
    pip install gdown python-magic      (Linux/Mac)

Использование:
    python gdrive_loader.py --url "https://drive.google.com/file/d/.../view"

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
# Download
# --------------------------------------------------
def download_file(url: str) -> str:
    output = os.path.join(ARCHIVE_DIR, "archive")
    logging.info(f"Downloading: {url}")
    path = gdown.download(url, output, fuzzy=True)
    if not path or not os.path.exists(path):
        raise Exception("Файл не скачался. Проверь ссылку и доступ (Общий доступ -> Все у кого есть ссылка)")
    logging.info(f"Downloaded to: {path}")
    return path

# --------------------------------------------------
# Detect & Extract
# --------------------------------------------------
def detect_archive_type(path: str) -> str:
    if MAGIC_AVAILABLE:
        try:
            mime = magic.from_file(path, mime=True)
            if mime == "application/zip":
                return "zip"
            if mime == "application/x-tar":
                return "tar"
            if mime in ["application/gzip", "application/x-gzip"]:
                return "tar.gz"
        except Exception as e:
            logging.warning(f"MIME detection failed: {e}")

    with open(path, "rb") as f:
        sig = f.read(8)
    if sig.startswith(b"PK"):
        return "zip"
    if sig.startswith(b"\x1f\x8b"):
        return "tar.gz"
    return "unknown"


def safe_extract_zip(path: str):
    with zipfile.ZipFile(path) as z:
        for member in z.infolist():
            extracted_path = os.path.join(EXTRACT_DIR, member.filename)
            if not os.path.realpath(extracted_path).startswith(os.path.realpath(EXTRACT_DIR)):
                raise Exception("Zip Slip detected")
        z.extractall(EXTRACT_DIR)


def safe_extract_tar(path: str, mode: str):
    with tarfile.open(path, mode) as tar:
        for member in tar.getmembers():
            member_path = os.path.join(EXTRACT_DIR, member.name)
            if not os.path.realpath(member_path).startswith(os.path.realpath(EXTRACT_DIR)):
                raise Exception("Tar Path Traversal detected")
        tar.extractall(EXTRACT_DIR)


def extract_archive(path: str):
    t = detect_archive_type(path)
    logging.info(f"Archive type: {t}")
    print(f"  Тип архива: {t}")

    if t == "zip":
        safe_extract_zip(path)
    elif t == "tar":
        safe_extract_tar(path, "r:")
    elif t == "tar.gz":
        safe_extract_tar(path, "r:gz")
    else:
        raise Exception(f"Неподдерживаемый формат: {t}")

    logging.info("Extraction finished")

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
    candidates = CSV_NAMES[key]
    for root, dirs, files in os.walk(EXTRACT_DIR):
        for f in files:
            if f.lower() in candidates:
                found = os.path.join(root, f)
                logging.info(f"Found {key}: {found}")
                return found

    # показываем что реально есть в архиве
    found_files = []
    for root, dirs, files in os.walk(EXTRACT_DIR):
        for f in files:
            found_files.append(os.path.relpath(os.path.join(root, f), EXTRACT_DIR))

    raise FileNotFoundError(
        f"Не найден файл для '{key}'. Ожидались: {candidates}\n"
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
    parser.add_argument("--url", default=DEFAULT_URL, help="Ссылка на архив в Google Drive")
    args = parser.parse_args()

    url = args.url or DEFAULT_URL
    if not url:
        print("Укажи ссылку: python gdrive_loader.py --url 'https://drive.google.com/...'")
        return

    setup()

    print("\n1. Скачиваем архив...")
    archive = download_file(url)
    checksum = sha256(archive)
    print(f"   SHA256: {checksum}")
    logging.info(f"SHA256: {checksum}")

    print("\n2. Распаковываем...")
    extract_archive(archive)

    print("\n3. Очищаем лишние файлы...")
    cleanup_files()

    print("\n4. Ищем CSV файлы...")
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
    print("\nГотово! Теперь запусти:")
    print("  python run.py")
    print("  python analyze.py")


if __name__ == "__main__":
    main()
