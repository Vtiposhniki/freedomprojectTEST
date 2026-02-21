# analyze.py
import json
import os
import re
from collections import Counter
from typing import Dict, Any, Tuple, Optional

import pandas as pd


# -----------------------------
# Paths
# -----------------------------
DEFAULT_ASSIGNMENTS = os.path.join("out", "assignments.csv")
DEFAULT_REPORT = os.path.join("out", "analysis_report.json")


# -----------------------------
# Text utils
# -----------------------------
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
    t = str(text).lower()
    # слова на латинице/кириллице + цифры
    words = re.findall(r"[a-zа-яё0-9]+", t, flags=re.IGNORECASE)
    out = []
    for w in words:
        w = w.strip()
        if len(w) <= 2:
            continue
        if w in RU_STOP or w in EN_STOP:
            continue
        out.append(w)
    return out


# -----------------------------
# Stats utils
# -----------------------------
def safe_float(x) -> Optional[float]:
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def gini(values: list[int]) -> float:
    # Gini coefficient for non-negative values
    if not values:
        return 0.0
    vals = sorted(max(0, int(v)) for v in values)
    n = len(vals)
    s = sum(vals)
    if s == 0:
        return 0.0
    cum = 0
    for i, v in enumerate(vals, start=1):
        cum += i * v
    return (2 * cum) / (n * s) - (n + 1) / n


def escalation_flag(row: pd.Series) -> bool:
    m = str(row.get("manager", "")).strip().upper()
    if m == "CAPITAL_ESCALATION":
        return True
    # fallback: try parse trace json
    tr = row.get("trace", "")
    try:
        obj = json.loads(tr) if isinstance(tr, str) and tr else {}
        return bool(obj.get("escalation", False))
    except Exception:
        return False


def agg_block(df: pd.DataFrame, key: str) -> Dict[str, Any]:
    """
    Generic aggregation:
    count, escalation_rate, avg_priority
    """
    if key not in df.columns:
        return {}

    grp = df.groupby(key, dropna=False)
    out = {}
    for k, g in grp:
        out[str(k)] = {
            "count": int(len(g)),
            "escalations": int(g["is_escalation"].sum()),
            "escalation_rate": float(round(g["is_escalation"].mean() * 100, 2)),
            "avg_priority": float(round(g["priority"].mean(), 2)) if "priority" in g.columns else None,
        }
    return out


# -----------------------------
# Main
# -----------------------------
def main():
    assignments_path = DEFAULT_ASSIGNMENTS
    if not os.path.exists(assignments_path):
        if os.path.exists("assignments.csv"):
            assignments_path = "assignments.csv"
        else:
            raise FileNotFoundError(
                f"Assignments not found. Expected '{DEFAULT_ASSIGNMENTS}' or 'assignments.csv'"
            )

    df = pd.read_csv(assignments_path)

    # Ensure columns exist
    for col in ["ai_type", "ai_lang", "priority", "sentiment", "office", "manager", "office_reason", "distance_km", "summary", "trace"]:
        if col not in df.columns:
            df[col] = ""

    # priority numeric
    df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(0).astype(int)

    # distance numeric (optional)
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce")

    # escalation
    df["is_escalation"] = df.apply(escalation_flag, axis=1)

    # Basic totals
    total = int(len(df))
    escalations = int(df["is_escalation"].sum())
    escalation_rate = float(round((escalations / total) * 100, 2)) if total else 0.0

    # Manager load (exclude escalations)
    non_esc = df[~df["is_escalation"]].copy()
    per_manager = non_esc["manager"].astype(str).value_counts()
    manager_load = {str(k): int(v) for k, v in per_manager.items()}

    loads = list(manager_load.values())
    fairness = {
        "managers_with_tickets": int(len(loads)),
        "min": int(min(loads)) if loads else 0,
        "max": int(max(loads)) if loads else 0,
        "avg": float(round(sum(loads) / len(loads), 3)) if loads else 0.0,
        "std": float(round(float(pd.Series(loads).std(ddof=0)) if loads else 0.0, 3)),
        "gini": float(round(gini(loads), 4)),
    }

    # Geo / office reason
    office_reason_stats = agg_block(df, "office_reason")
    # avg distance for by_distance subset
    by_dist = df[df["office_reason"].astype(str) == "by_distance"]
    avg_dist = None
    if len(by_dist) and by_dist["distance_km"].notna().any():
        avg_dist = float(round(by_dist["distance_km"].dropna().mean(), 2))

    # Sentiment analytics
    by_sentiment = agg_block(df, "sentiment")
    by_office = agg_block(df, "office")
    by_type = agg_block(df, "ai_type")
    by_lang = agg_block(df, "ai_lang")

    # Escalation vs sentiment breakdown
    esc_by_sent = {}
    for s, g in df.groupby("sentiment", dropna=False):
        esc_by_sent[str(s)] = {
            "count": int(len(g)),
            "escalations": int(g["is_escalation"].sum()),
            "escalation_rate": float(round(g["is_escalation"].mean() * 100, 2)),
        }

    # Top tokens for NEG
    neg_df = df[df["sentiment"].astype(str).str.upper() == "NEG"]
    tokens = []
    for t in neg_df["summary"].astype(str).tolist():
        tokens.extend(tokenize(t))
    top_neg_words = [{"word": w, "count": c} for w, c in Counter(tokens).most_common(30)]

    report: Dict[str, Any] = {
        "source_file": assignments_path,
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
        "escalation_by_sentiment": esc_by_sent,
        "geo": {
            "office_reason": office_reason_stats,
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

    # Console summary
    print("\n=== ANALYSIS SUMMARY ===")
    print(f"Input: {assignments_path}")
    print(f"Total tickets: {total}")
    print(f"Escalations: {escalations} ({escalation_rate}%)")
    print(f"Average priority: {report['totals']['avg_priority']}")
    print(f"Managers w/ tickets: {fairness['managers_with_tickets']}")
    print(f"Load fairness: std={fairness['std']}, gini={fairness['gini']}")
    if avg_dist is not None:
        print(f"Avg distance (by_distance): {avg_dist} km")
    print(f"Saved report: {DEFAULT_REPORT}\n")


if __name__ == "__main__":
    main()