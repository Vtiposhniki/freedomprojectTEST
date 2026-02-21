#!/usr/bin/env python3
"""
patch_addresses.py
------------------
Разовый скрипт — заполняет пустые адреса офисов в БД из встроенного справочника.

Запуск:
    python patch_addresses.py
"""
from db import patch_office_addresses

if __name__ == "__main__":
    print("Патчим адреса офисов...")
    updated = patch_office_addresses()
    if updated == 0:
        print("Все адреса уже заполнены или офисы не найдены.")
    else:
        print(f"Готово — обновлено {updated} офисов.")
        print("Перезапустите API: uvicorn api:app --reload")