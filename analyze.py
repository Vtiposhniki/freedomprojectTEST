# analyze.py
"""
Анализ результатов распределения тикетов.
Читает данные из PostgreSQL (таблица assignments + view v_assignments_full).
Сохраняет JSON-отчёт в out/analysis_report.json.

Использование:
    python analyze.py
"""

import json
import os
import re
from collections import Counter
from typing import Dict, Any, Optional

import pandas as pd

# -------------------------------------------------------
# Paths
# -------------------------------------------------------
DEFAULT_REPORT = os.path.join("out", "analysis_report.json")

# -------------------------------------------------------
# Text utils
# -------------------------------------------------------
RU_STOP = {
    "и", "в", "во", "на", "но", "а", "я", "мы", "вы", "он", "она", "они",
    "это", "то", "же", "как", "что", "чтобы", "к", "ко", "с", "со", "за",
    "у", "от", "до", "по", "из", "или", "ли", "не", "нет", "да", "ну",
    "при", "для", "про", "над", "под", "там", "тут", "здесь",
    "меня", "мне", "мой", "моя", "мои", "ваш", "ваша", "ваши",
    "пожалуйста", "здравствуйте", "добрый", "день", "вечер", "привет",
}
EN_STOP = {
    "the", "a", "an", "and", "or", "to", "in", "on", "at", "for", "of", "with",
    "i", "you", "we", "they", "he", "she", "it", "is", "are", "was", "were",
    "my", "your", "our", "their", "please", "hello", "hi",
}


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    words = re.findall(r"[a-zа-яё0-9]+", str(text).lower(), flags=re.IGNORECASE)
    return [
        w for w in words
        if len(w) > 2 and w not in RU_STOP and w not in EN_STOP
    ]


# -------------------------------------------------------
# Stats utils
# -------------------------------------------------------
def gini(values: list[int]) -> float:
    if not values:
        return 0.0
    vals = sorted(max(0, int(v)) for v in values)
    n = len(vals)
    s = sum(vals)
    if s == 0:
        return 0.0
    cum = sum(i * v for i, v in enumerate(vals, start=1))
    return (2 * cum) / (n * s) - (n + 1) / n


def agg_block(df: pd.DataFrame, key: str) -> Dict[str, Any]:
    if key not in df.columns:
        return {}
    out = {}
    for k, g in df.groupby(key, dropna=False):
        out[str(k)] = {
            "count": int(len(g)),
            "escalations": int(g["is_escalation"].sum()),
            "escalation_rate_pct": float(round(g["is_escalation"].mean() * 100, 2)),
            "avg_priority": float(round(g["priority"].mean(), 2)) if "priority" in g.columns else None,
        }
    return out


# -------------------------------------------------------
# Load from DB
# -------------------------------------------------------
def load_from_db() -> pd.DataFrame:
    """Читает v_assignments_full из PostgreSQL."""
    from db import get_connection
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT
                guid,
                segment,
                country,
                city,
                ai_type,
                ai_lang,
                sentiment,
                priority,
                summary,
                recommendation,
                office,
                office_reason,
                distance_km,
                is_escalation,
                manager,
                manager_position,
                manager_skills,
                assigned_at,
                trace
            FROM v_assignments_full
        """, conn)
        return df
    finally:
        conn.close()


# -------------------------------------------------------
# Load from CSV (fallback)
# -------------------------------------------------------
def load_from_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["ai_type", "ai_lang", "priority", "sentiment", "office",
                "manager", "office_reason", "distance_km", "summary", "trace"]:
        if col not in df.columns:
            df[col] = ""
    df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(0).astype(int)
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce")
    # escalation из поля manager или trace
    def _esc(row):
        if str(row.get("manager", "")).strip().upper() == "CAPITAL_ESCALATION":
            return True
        try:
            obj = json.loads(row.get("trace", "") or "{}")
            return bool(obj.get("escalation", False))
        except Exception:
            return False
    df["is_escalation"] = df.apply(_esc, axis=1)
    return df


# -------------------------------------------------------
# Main
# -------------------------------------------------------
def main():
    # --- Источник данных: сначала БД, потом CSV ---
    df: Optional[pd.DataFrame] = None
    source_label = ""

    try:
        print("Подключаемся к БД...")
        df = load_from_db()
        source_label = "postgresql:v_assignments_full"
        print(f"  Загружено из БД: {len(df)} записей")
    except Exception as e:
        print(f"  БД недоступна: {e}")
        print("  Пробуем CSV fallback...")

    if df is None or df.empty:
        csv_path = os.path.join("out", "assignments.csv")
        if not os.path.exists(csv_path):
            csv_path = "assignments.csv"
        if os.path.exists(csv_path):
            df = load_from_csv(csv_path)
            source_label = csv_path
            print(f"  Загружено из CSV: {len(df)} записей")
        else:
            print("Нет данных: ни БД, ни CSV не доступны.")
            return

    # --- Нормализация ---
    df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(0).astype(int)
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce")
    df["is_escalation"] = df["is_escalation"].astype(bool)

    total = int(len(df))
    escalations = int(df["is_escalation"].sum())
    escalation_rate = float(round((escalations / total) * 100, 2)) if total else 0.0

    # --- Нагрузка менеджеров (без эскалаций) ---
    non_esc = df[~df["is_escalation"]].copy()
    per_manager = non_esc["manager"].astype(str).value_counts()
    manager_load = {str(k): int(v) for k, v in per_manager.items()}
    loads = list(manager_load.values())

    fairness = {
        "managers_with_tickets": int(len(loads)),
        "min": int(min(loads)) if loads else 0,
        "max": int(max(loads)) if loads else 0,
        "avg": float(round(sum(loads) / len(loads), 3)) if loads else 0.0,
        "std": float(round(float(pd.Series(loads).std(ddof=0)), 3)) if loads else 0.0,
        "gini": float(round(gini(loads), 4)),
    }

    # --- Агрегации ---
    by_office    = agg_block(df, "office")
    by_type      = agg_block(df, "ai_type")
    by_lang      = agg_block(df, "ai_lang")
    by_sentiment = agg_block(df, "sentiment")
    by_reason    = agg_block(df, "office_reason")

    # --- Среднее расстояние при маршрутизации by_distance ---
    by_dist = df[df["office_reason"].astype(str) == "by_distance"]
    avg_dist = None
    if len(by_dist) and by_dist["distance_km"].notna().any():
        avg_dist = float(round(by_dist["distance_km"].dropna().mean(), 2))

    # --- Топ-слова из негативных тикетов ---
    neg_df = df[df["sentiment"].astype(str).str.upper() == "NEG"]
    tokens = []
    for t in neg_df["summary"].astype(str).tolist():
        tokens.extend(tokenize(t))
    top_neg_words = [{"word": w, "count": c} for w, c in Counter(tokens).most_common(30)]

    # --- Приоритеты ---
    priority_dist = {
        str(k): int(v)
        for k, v in df["priority"].value_counts().sort_index().items()
    }

    # --- Сборка отчёта ---
    report: Dict[str, Any] = {
        "source": source_label,
        "totals": {
            "tickets": total,
            "escalations": escalations,
            "escalation_rate_pct": escalation_rate,
            "avg_priority": float(round(df["priority"].mean(), 2)) if total else 0.0,
        },
        "by_office": by_office,
        "by_type": by_type,
        "by_lang": by_lang,
        "by_sentiment": by_sentiment,
        "by_priority": priority_dist,
        "geo": {
            "office_reason": by_reason,
            "avg_distance_km_when_by_distance": avg_dist,
        },
        "managers": {
            "load_counts": manager_load,
            "fairness": fairness,
        },
        "neg_insights": {
            "top_words": top_neg_words,
        },
    }

    os.makedirs("out", exist_ok=True)
    with open(DEFAULT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # --- Консольный вывод ---
    print("\n=== ANALYSIS SUMMARY ===")
    print(f"Source:          {source_label}")
    print(f"Total tickets:   {total}")
    print(f"Escalations:     {escalations} ({escalation_rate}%)")
    print(f"Avg priority:    {report['totals']['avg_priority']}")
    print(f"Managers active: {fairness['managers_with_tickets']}")
    print(f"Load fairness:   std={fairness['std']}, gini={fairness['gini']}")
    if avg_dist is not None:
        print(f"Avg dist (geo):  {avg_dist} km")
    print(f"\nReport saved → {DEFAULT_REPORT}")


if __name__ == "__main__":
    main()