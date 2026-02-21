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

    # Сериализуем
    df["assigned_at"] = df["assigned_at"].astype(str)
    df["is_escalation"] = df["is_escalation"].astype(bool)
    return df.to_dict(orient="records")


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
    row = df.iloc[0].to_dict()
    row["assigned_at"] = str(row["assigned_at"])
    row["is_escalation"] = bool(row["is_escalation"])
    return row


# ─────────────────────────────────────────────
# ГЕО
# ─────────────────────────────────────────────

@app.get("/geo/tickets")
def get_geo_tickets():
    """Тикеты с координатами для карты."""
    df = query_df("""
        SELECT v.guid, v.city, v.office, v.ai_type, v.sentiment,
               v.priority, v.is_escalation,
               a.lat, a.lon
        FROM v_assignments_full v
        JOIN tickets t ON t.guid = v.guid
        JOIN ai_analysis a ON a.ticket_id = t.id
        WHERE a.lat IS NOT NULL AND a.lon IS NOT NULL
    """)
    df["is_escalation"] = df["is_escalation"].astype(bool)
    return df.to_dict(orient="records")


@app.get("/geo/offices")
def get_geo_offices():
    df = query_df("SELECT name, address, lat, lon FROM offices WHERE lat IS NOT NULL")
    return df.to_dict(orient="records")


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
    # Собираем контекст из БД
    summary = get_summary()
    by_type = get_by_type()
    by_office = get_by_office()
    by_sentiment = get_by_sentiment()
    manager_load = get_manager_load()

    context = f"""
Ты — аналитик данных колл-центра Freedom Finance. У тебя есть следующие актуальные данные:

📊 ОБЩАЯ СТАТИСТИКА:
- Всего тикетов: {summary.get('total_tickets')}
- Эскалаций: {summary.get('escalations')} ({summary.get('escalation_rate_pct')}%)
- Средний приоритет: {summary.get('avg_priority')}
- Негативный сентимент: {summary.get('negative_sentiment_pct')}%
- Офисов: {summary.get('unique_offices')}
- Менеджеров: {summary.get('unique_managers')}

📋 ПО ТИПАМ ОБРАЩЕНИЙ:
{json.dumps(by_type, ensure_ascii=False, indent=2)}

🏢 ПО ОФИСАМ:
{json.dumps(by_office, ensure_ascii=False, indent=2)}

😊 ПО СЕНТИМЕНТУ:
{json.dumps(by_sentiment, ensure_ascii=False, indent=2)}

👥 НАГРУЗКА МЕНЕДЖЕРОВ (топ-10):
{json.dumps(manager_load[:10], ensure_ascii=False, indent=2)}

Отвечай на русском языке. Будь конкретным, используй числа из данных.
Если вопрос про тренды или прогнозы — честно скажи что данных для этого недостаточно.
"""

    client = get_client()
    if client is None:
        # Fallback — rule-based ответы
        return {"answer": _rule_based_answer(req.question, summary, by_type, by_office)}

    messages = [{"role": "system", "content": context}]
    for msg in req.history[-6:]:  # последние 6 сообщений истории
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
        return {"answer": _rule_based_answer(req.question, summary, by_type, by_office), "source": "fallback", "error": str(e)}


def _rule_based_answer(question: str, summary: dict, by_type: list, by_office: list) -> str:
    """Простые rule-based ответы если LLM недоступен."""
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