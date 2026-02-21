# db.py
"""
Все операции с PostgreSQL:
- init_db()         — создать таблицы
- load_csv()        — загрузить CSV файлы в БД (один раз)
- get_tickets_df()  — прочитать тикеты из БД в DataFrame
- get_managers_df() — прочитать менеджеров из БД в DataFrame
- get_offices_df()  — прочитать офисы из БД в DataFrame
- save_results()    — записать результат распределения в БД
"""

import os
import json
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


# -------------------------------------------------------
# Подключение
# -------------------------------------------------------

def get_connection():
    return psycopg2.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = int(os.getenv("DB_PORT", "5432")),
        dbname   = os.getenv("DB_NAME",     "fire_db"),
        user     = os.getenv("DB_USER",     "postgres"),
        password = os.getenv("DB_PASSWORD", ""),
    )


def init_db():
    """Создать все таблицы из schema.sql."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("[DB] Schema OK")
    finally:
        conn.close()


# -------------------------------------------------------
# ЗАГРУЗКА CSV → БД  (запускается один раз)
# -------------------------------------------------------

def load_csv(
    tickets_path  = "tickets.csv",
    managers_path = "managers.csv",
    units_path    = "business_units.csv",
):
    """
    Читает три CSV файла и загружает их в БД.
    Запускать один раз. При повторном запуске дубли игнорируются.
    """
    from ai.geo import GeoNormalizer
    geo = GeoNormalizer()

    tickets_df  = pd.read_csv(tickets_path)
    managers_df = pd.read_csv(managers_path)
    units_df    = pd.read_csv(units_path)

    # нормализуем заголовки
    tickets_df.columns  = tickets_df.columns.str.strip().str.lower().str.replace("ё", "е")
    managers_df.columns = managers_df.columns.str.strip().str.lower().str.replace("ё", "е")
    units_df.columns    = units_df.columns.str.strip().str.lower().str.replace("ё", "е")

    conn = get_connection()
    try:
        with conn.cursor() as cur:

            # --- Офисы ---
            office_map = {}
            for _, row in units_df.iterrows():
                name    = str(row.get("офис", "")).strip()
                address = str(row.get("адрес", "")).strip()
                lat, lon = geo.geocode(name)
                cur.execute("""
                    INSERT INTO offices (name, address, lat, lon)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET address=EXCLUDED.address
                    RETURNING id
                """, (name, address, lat, lon))
                office_map[name] = cur.fetchone()[0]
            print(f"[DB] Offices loaded: {len(office_map)}")

            # --- Менеджеры ---
            for _, row in managers_df.iterrows():
                name     = str(row.get("фио", "")).strip()
                position = str(row.get("должность", "")).strip()
                office_n = str(row.get("офис", "")).strip()
                skills_s = str(row.get("навыки", "")).strip()
                load_val = int(row.get("количество обращений в работе", 0) or 0)
                skills   = [s.strip() for s in skills_s.replace(";", ",").split(",") if s.strip()]
                office_id = office_map.get(office_n)
                cur.execute("""
                    INSERT INTO managers (name, position, office_id, skills, load)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                """, (name, position, office_id, skills, load_val))
            print(f"[DB] Managers loaded: {len(managers_df)}")

            # --- Тикеты ---
            count = 0
            for _, row in tickets_df.iterrows():
                guid = str(row.get("guid клиента", "")).strip()
                if not guid:
                    continue

                # дата рождения
                bd = row.get("дата рождения", None)
                birth_date = None
                if pd.notna(bd):
                    try:
                        birth_date = pd.to_datetime(bd).date()
                    except Exception:
                        pass

                cur.execute("""
                    INSERT INTO tickets
                        (guid, gender, birth_date, description, attachment,
                         segment, country, region, city, street, house)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (guid) DO NOTHING
                """, (
                    guid,
                    str(row.get("пол клиента", "") or ""),
                    birth_date,
                    str(row.get("описание", "") or ""),
                    str(row.get("вложения", "") or ""),
                    str(row.get("сегмент клиента", "") or ""),
                    str(row.get("страна", "") or ""),
                    str(row.get("область", "") or ""),
                    str(row.get("населенный пункт", "") or ""),
                    str(row.get("улица", "") or ""),
                    str(row.get("дом", "") or ""),
                ))
                count += 1
            print(f"[DB] Tickets loaded: {count}")

        conn.commit()
        print("[DB] CSV import done ✅")
    finally:
        conn.close()


# -------------------------------------------------------
# ЧТЕНИЕ ИЗ БД → DataFrame  (используется в run.py)
# -------------------------------------------------------

def get_tickets_df() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT
                guid,
                description,
                segment,
                country,
                city,
                gender,
                birth_date,
                region,
                street,
                house
            FROM tickets
        """, conn)
        return df
    finally:
        conn.close()


def get_managers_df() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT
                m.name      AS "ФИО",
                m.position  AS "Должность ",
                o.name      AS "Офис",
                array_to_string(m.skills, ', ') AS "Навыки",
                m.load      AS "Количество обращений в работе"
            FROM managers m
            LEFT JOIN offices o ON o.id = m.office_id
        """, conn)
        return df
    finally:
        conn.close()


def get_offices_df() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT name AS \"Офис\", address AS \"Адрес\" FROM offices", conn)
        return df
    finally:
        conn.close()


# -------------------------------------------------------
# СОХРАНЕНИЕ РЕЗУЛЬТАТОВ → БД
# -------------------------------------------------------

def save_results(result_df: pd.DataFrame):
    """Записать итоговые assignments в БД."""
    conn = get_connection()
    saved = 0
    try:
        with conn.cursor() as cur:

            # Загружаем маппинги из БД
            cur.execute("SELECT name, id FROM offices")
            office_map = {row[0]: row[1] for row in cur.fetchall()}

            cur.execute("SELECT name, id FROM managers")
            manager_map = {row[0]: row[1] for row in cur.fetchall()}

            for _, row in result_df.iterrows():
                guid = str(row["guid"])

                # ticket_id
                cur.execute("SELECT id FROM tickets WHERE guid = %s", (guid,))
                res = cur.fetchone()
                if not res:
                    continue
                ticket_id = res[0]

                # ai_analysis
                cur.execute("""
                    INSERT INTO ai_analysis
                        (ticket_id, ai_type, ai_lang, sentiment,
                         priority, summary, recommendation, lat, lon)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (
                    ticket_id,
                    str(row.get("ai_type", "")),
                    str(row.get("ai_lang", "")),
                    str(row.get("sentiment", "")),
                    int(row.get("priority", 5)),
                    str(row.get("summary", "")),
                    str(row.get("recommendation", "")),
                    row.get("lat") or None,
                    row.get("lon") or None,
                ))
                ai_id = cur.fetchone()[0]

                # assignment
                manager_name  = str(row.get("manager", ""))
                is_escalation = manager_name == "CAPITAL_ESCALATION"
                manager_id    = manager_map.get(manager_name) if not is_escalation else None
                office_id     = office_map.get(str(row.get("office", "")))

                trace = row.get("trace", "{}")
                if isinstance(trace, str):
                    try:
                        trace = json.loads(trace)
                    except Exception:
                        trace = {}

                cur.execute("""
                    INSERT INTO assignments
                        (ticket_id, ai_analysis_id, manager_id, office_id,
                         office_reason, distance_km, is_escalation, trace)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    ticket_id, ai_id, manager_id, office_id,
                    str(row.get("office_reason", "")),
                    row.get("distance_km") or None,
                    is_escalation,
                    json.dumps(trace, ensure_ascii=False),
                ))
                saved += 1

        conn.commit()
        print(f"[DB] Assignments saved: {saved} ✅")
    finally:
        conn.close()
