# load_csv.py
"""
Запускается ОДИН РАЗ для загрузки CSV файлов в базу данных.
После этого CSV файлы можно удалить — все данные будут в БД.

Использование:
    python load_csv.py
    python load_csv.py --tickets my_tickets.csv  (свой файл)
"""

import argparse
from db import init_db, load_csv

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets",  default="tickets.csv")
    parser.add_argument("--managers", default="managers.csv")
    parser.add_argument("--units",    default="business_units.csv")
    args = parser.parse_args()

    print("Инициализация схемы БД...")
    init_db()

    print(f"\nЗагрузка файлов:")
    print(f"  tickets:  {args.tickets}")
    print(f"  managers: {args.managers}")
    print(f"  units:    {args.units}\n")

    load_csv(
        tickets_path  = args.tickets,
        managers_path = args.managers,
        units_path    = args.units,
    )
