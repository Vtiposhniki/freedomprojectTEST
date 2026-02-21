# api.py
"""
FastAPI backend для FIRE Engine Dashboard.
Проксирует данные из PostgreSQL во фронтенд.

Запуск:
    uvicorn api:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import numpy as np
import json
import os
import sys
from functools import lru_cache
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import get_connection
from ai.llm_client import get_client

app = FastAPI(title="FIRE Engine API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Простой in-memory кеш ──
_cache: dict = {}
_cache_ttl = 60  # секунд

def cached_query(key: str, sql: str, params=None):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < _cache_ttl:
        return _cache[key]["data"]
    df = query_df(sql, params)
    _cache[key] = {"data": df, "ts": now}
    return df


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def query_df(sql: str, params=None) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def safe_serialize(df: pd.DataFrame) -> list:
    """
    Безопасная сериализация DataFrame в список словарей.
    Обрабатывает NaT, NaN, numpy типы, Timestamp.
    """
    records = []
    for _, row in df.iterrows():
        record = {}
        for col, val in row.items():
            if pd.isna(val) if not isinstance(val, (list, dict)) else False:
                record[col] = None
            elif hasattr(val, 'isoformat'):
                # Timestamp, datetime
                record[col] = val.isoformat()
            elif isinstance(val, (np.integer,)):
                record[col] = int(val)
            elif isinstance(val, (np.floating,)):
                record[col] = float(val) if not np.isnan(val) else None
            elif isinstance(val, (np.bool_,)):
                record[col] = bool(val)
            elif isinstance(val, np.ndarray):
                record[col] = val.tolist()
            else:
                record[col] = val
        records.append(record)
    return records


# ─────────────────────────────────────────────
# ЭНДПОИНТЫ: ОБЩАЯ СТАТИСТИКА
# ─────────────────────────────────────────────

@app.get("/stats/summary")
def get_summary():
    df = cached_query("summary", "SELECT * FROM v_assignments_full")
    if df.empty:
        return {}

    total = len(df)
    escalations = int(df["is_escalation"].sum())
    avg_priority = round(float(df["priority"].mean()), 2)
    neg_pct = round(float((df["sentiment"] == "NEG").mean() * 100), 1)

    return {
        "total_tickets": total,
        "escalations": escalations,
        "escalation_rate_pct": round(escalations / total * 100, 2),
        "avg_priority": avg_priority,
        "negative_sentiment_pct": neg_pct,
        "unique_offices": int(df["office"].nunique()),
        "unique_managers": int(df["manager"].nunique()),
    }


@app.get("/stats/by_type")
def get_by_type():
    df = cached_query("by_type", """
        SELECT ai_type, COUNT(*) as count,
               ROUND(AVG(priority)::numeric, 2) as avg_priority,
               SUM(CASE WHEN is_escalation THEN 1 ELSE 0 END) as escalations
        FROM v_assignments_full
        GROUP BY ai_type
        ORDER BY count DESC
    """)
    return df.to_dict(orient="records")


@app.get("/stats/by_office")
def get_by_office():
    df = cached_query("by_office", """
        SELECT office, COUNT(*) as tickets,
               SUM(CASE WHEN is_escalation THEN 1 ELSE 0 END) as escalations,
               ROUND(AVG(priority)::numeric, 2) as avg_priority
        FROM v_assignments_full
        GROUP BY office
        ORDER BY tickets DESC
    """)
    return df.to_dict(orient="records")


@app.get("/stats/by_sentiment")
def get_by_sentiment():
    df = cached_query("by_sentiment", """
        SELECT sentiment, COUNT(*) as count
        FROM v_assignments_full
        GROUP BY sentiment
        ORDER BY count DESC
    """)
    return df.to_dict(orient="records")


@app.get("/stats/by_lang")
def get_by_lang():
    df = cached_query("by_lang", """
        SELECT ai_lang, COUNT(*) as count
        FROM v_assignments_full
        GROUP BY ai_lang
        ORDER BY count DESC
    """)
    return df.to_dict(orient="records")


@app.get("/stats/by_priority")
def get_by_priority():
    df = cached_query("by_priority", """
        SELECT priority, COUNT(*) as count
        FROM v_assignments_full
        GROUP BY priority
        ORDER BY priority
    """)
    return df.to_dict(orient="records")


# ─────────────────────────────────────────────
# МЕНЕДЖЕРЫ
# ─────────────────────────────────────────────

@app.get("/managers/load")
def get_manager_load():
    df = cached_query("manager_load", """
        SELECT manager, office, COUNT(*) as tickets,
               SUM(CASE WHEN is_escalation THEN 1 ELSE 0 END) as escalations
        FROM v_assignments_full
        WHERE manager != 'CAPITAL_ESCALATION'
        GROUP BY manager, office
        ORDER BY tickets DESC
    """)
    return df.to_dict(orient="records")


@app.get("/managers/fairness")
def get_fairness():
    df = cached_query("fairness", """
        SELECT office,
               COUNT(DISTINCT manager) as managers,
               COUNT(*) as tickets,
               ROUND(AVG(cnt)::numeric, 2) as mean_load
        FROM (
            SELECT office, manager, COUNT(*) as cnt
            FROM v_assignments_full
            WHERE manager != 'CAPITAL_ESCALATION'
            GROUP BY office, manager
        ) sub
        GROUP BY office
        ORDER BY tickets DESC
    """)
    return df.to_dict(orient="records")


# ─────────────────────────────────────────────
# ТИКЕТЫ
# ─────────────────────────────────────────────

@app.get("/tickets")
def get_tickets(
    office: Optional[str] = None,
    ai_type: Optional[str] = None,
    sentiment: Optional[str] = None,
    ai_lang: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    """Список тикетов с фильтрацией."""
    conditions = []
    params = {}

    if office:
        conditions.append("office = %(office)s")
        params["office"] = office
    if ai_type:
        conditions.append("ai_type = %(ai_type)s")
        params["ai_type"] = ai_type
    if sentiment:
        conditions.append("sentiment = %(sentiment)s")
        params["sentiment"] = sentiment
    if ai_lang:
        conditions.append("ai_lang = %(ai_lang)s")
        params["ai_lang"] = ai_lang

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params["limit"] = limit
    params["offset"] = offset

    try:
        df = query_df(f"""
            SELECT guid, segment, country, city, ai_type, ai_lang,
                   sentiment, priority, summary, recommendation,
                   office, office_reason, distance_km, is_escalation,
                   manager, manager_position, assigned_at
            FROM v_assignments_full
            {where}
            ORDER BY priority DESC, assigned_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """, params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return safe_serialize(df)


@app.get("/tickets/count")
def get_tickets_count(
    office: Optional[str] = None,
    ai_type: Optional[str] = None,
    sentiment: Optional[str] = None,
    ai_lang: Optional[str] = None,
):
    conditions = []
    params = {}
    if office:
        conditions.append("office = %(office)s")
        params["office"] = office
    if ai_type:
        conditions.append("ai_type = %(ai_type)s")
        params["ai_type"] = ai_type
    if sentiment:
        conditions.append("sentiment = %(sentiment)s")
        params["sentiment"] = sentiment
    if ai_lang:
        conditions.append("ai_lang = %(ai_lang)s")
        params["ai_lang"] = ai_lang

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    df = query_df(f"SELECT COUNT(*) as cnt FROM v_assignments_full {where}", params)
    return {"count": int(df["cnt"].iloc[0])}


@app.get("/tickets/{guid}")
def get_ticket(guid: str):
    df = query_df("""
        SELECT * FROM v_assignments_full WHERE guid = %(guid)s
    """, {"guid": guid})
    if df.empty:
        raise HTTPException(status_code=404, detail="Ticket not found")
    records = safe_serialize(df)
    return records[0]


# ─────────────────────────────────────────────
# ГЕО
# ─────────────────────────────────────────────

@app.get("/geo/tickets")
def get_geo_tickets():
    """Тикеты — координаты тикета если есть, иначе координаты офиса."""
    df = query_df("""
        SELECT
            v.guid, v.city, v.office, v.ai_type, v.sentiment,
            v.priority, v.is_escalation,
            COALESCE(a.lat, o.lat) AS lat,
            COALESCE(a.lon, o.lon) AS lon
        FROM v_assignments_full v
        JOIN tickets t      ON t.guid = v.guid
        JOIN ai_analysis a  ON a.ticket_id = t.id
        LEFT JOIN offices o ON o.name = v.office
        WHERE COALESCE(a.lat, o.lat) IS NOT NULL
    """)
    return safe_serialize(df)


@app.get("/geo/offices")
def get_geo_offices():
    df = query_df("SELECT name, address, lat, lon FROM offices WHERE lat IS NOT NULL")
    if df.empty:
        return []

    # Справочник адресов — fallback если в БД пусто
    _ADDRESSES = {
        "актау":            "17-й микрорайон, Бизнес-центр «Urban», зд. 22",
        "актобе":            "пр. Алии Молдагуловой, 44",
        "алматы":            "пр-т Аль-Фараби, 77/7 БЦ «Esentai Tower», 7 этаж",
        "астана":            "Есиль район, Достық 16, БЦ «Talan Towers», 27 этаж",
        "атырау":            "ул. Студенческая 52, БЦ «Адал», 2 этаж, 201 офис",
        "караганда":            "пр. Нуркена Абдирова, ст 12 НП 3, 2 этаж",
        "кокшетау":            "пр-т Назарбаева, д. 4/2",
        "костанай":            "пр-т Аль-Фараби 65, 12 этаж, офис №1201",
        "кызылорда":            "ул. Кунаева 4, БЦ Прима Парк",
        "павлодар":            "ул. Луговая 16, «Дом инвесторов», 7 этаж",
        "петропавловск":            "ул. Букетова 31А",
        "тараз":            "ул. Желтоксан 86",
        "уральск":            "ул. Ескалиева, д. 177, оф. 505",
        "орал":            "ул. Ескалиева, д. 177, оф. 505",
        "усть-каменогорск":            "ул. Максима Горького, д. 50",
        "шымкент":            "ул. Кунаева, д. 59, 1 этаж",
    }

    def _get_address(name: str, current: str) -> str:
        if current and str(current).strip() not in ("", "nan", "none", "None"):
            return str(current).strip()
        key = str(name).lower().strip().replace("ё", "е")
        for prefix in ("г.", "город ", "city "):
            if key.startswith(prefix):
                key = key[len(prefix):].strip()
        return _ADDRESSES.get(key, "")

    records = safe_serialize(df)
    for r in records:
        r["address"] = _get_address(r.get("name", ""), r.get("address", ""))
    return records


@app.post("/geo/offices/patch_addresses")
def patch_office_addresses_endpoint():
    """Патч адресов офисов из встроенного справочника."""
    try:
        from db import patch_office_addresses
        updated = patch_office_addresses()
        _cache.clear()
        return {"updated": updated, "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# FILTERS META
# ─────────────────────────────────────────────

@app.get("/meta/filters")
def get_filters():
    offices = cached_query("meta_offices", "SELECT DISTINCT office FROM v_assignments_full WHERE office IS NOT NULL ORDER BY office")
    types   = cached_query("meta_types",   "SELECT DISTINCT ai_type FROM v_assignments_full WHERE ai_type IS NOT NULL ORDER BY ai_type")
    return {
        "offices":    offices["office"].tolist(),
        "ai_types":   types["ai_type"].tolist(),
        "sentiments": ["POS", "NEU", "NEG"],
        "languages":  ["RU", "KZ", "ENG"],
    }


# ─────────────────────────────────────────────
# AI CHAT
# ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list = []


@app.post("/ai/chat")
def ai_chat(req: ChatRequest):
    """AI-ассистент для аналитики — отвечает на вопросы по данным."""
    summary = get_summary()
    by_type = get_by_type()
    by_office = get_by_office()
    by_sentiment = get_by_sentiment()
    manager_load = get_manager_load()

    context = f"""
Ты — аналитик данных колл-центра Freedom Finance. У тебя есть следующие актуальные данные:

ОБЩАЯ СТАТИСТИКА:
- Всего тикетов: {summary.get('total_tickets')}
- Эскалаций: {summary.get('escalations')} ({summary.get('escalation_rate_pct')}%)
- Средний приоритет: {summary.get('avg_priority')}
- Негативный сентимент: {summary.get('negative_sentiment_pct')}%
- Офисов: {summary.get('unique_offices')}
- Менеджеров: {summary.get('unique_managers')}

ПО ТИПАМ ОБРАЩЕНИЙ:
{json.dumps(by_type, ensure_ascii=False, indent=2)}

ПО ОФИСАМ:
{json.dumps(by_office, ensure_ascii=False, indent=2)}

ПО СЕНТИМЕНТУ:
{json.dumps(by_sentiment, ensure_ascii=False, indent=2)}

НАГРУЗКА МЕНЕДЖЕРОВ (топ-10):
{json.dumps(manager_load[:10], ensure_ascii=False, indent=2)}

Отвечай на русском языке. Будь конкретным, используй числа из данных.
Если вопрос про тренды или прогнозы — честно скажи что данных для этого недостаточно.
"""

    client = get_client()
    if client is None:
        return {"answer": _rule_based_answer(req.question, summary, by_type, by_office)}

    messages = [{"role": "system", "content": context}]
    for msg in req.history[-6:]:
        messages.append(msg)
    messages.append({"role": "user", "content": req.question})

    try:
        response = client.chat.completions.create(
            model="qwen/qwen3-next-80b-a3b-instruct",
            messages=messages,
            temperature=0.3,
            max_tokens=600,
            timeout=20,
        )
        answer = response.choices[0].message.content or ""
        return {"answer": answer, "source": "llm"}
    except Exception as e:
        return {
            "answer": _rule_based_answer(req.question, summary, by_type, by_office),
            "source": "fallback",
            "error": str(e),
        }


def _rule_based_answer(question: str, summary: dict, by_type: list, by_office: list) -> str:
    q = question.lower()

    if any(w in q for w in ["сколько", "количество", "всего", "total"]):
        return (
            f"Всего тикетов: **{summary.get('total_tickets')}**\n"
            f"Эскалаций: **{summary.get('escalations')}** ({summary.get('escalation_rate_pct')}%)\n"
            f"Средний приоритет: **{summary.get('avg_priority')}**"
        )
    if any(w in q for w in ["офис", "город"]):
        top = by_office[0] if by_office else {}
        return f"Больше всего тикетов в офисе **{top.get('office')}**: {top.get('tickets')} шт."
    if any(w in q for w in ["тип", "категори", "жалоб", "консультаци"]):
        top = by_type[0] if by_type else {}
        return f"Самый частый тип: **{top.get('ai_type')}** — {top.get('count')} тикетов."
    if any(w in q for w in ["эскалаци", "escalat"]):
        return (
            f"Эскалаций: **{summary.get('escalations')}** из {summary.get('total_tickets')} "
            f"({summary.get('escalation_rate_pct')}%)"
        )

    return (
        "Я могу ответить на вопросы о количестве тикетов, офисах, типах обращений, "
        "менеджерах и эскалациях. Уточните ваш вопрос."
    )


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        conn = get_connection()
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    llm_ok = get_client() is not None

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "llm": llm_ok,
    }