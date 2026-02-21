# run.py
import os
import pandas as pd

from engine import FIREEngine
from ai.enricher import TicketEnricher


def pick_value(row, *possible_names):
    """Вернуть первое непустое значение из возможных имён колонок."""
    for name in possible_names:
        if name in row and pd.notna(row[name]) and str(row[name]).strip():
            return str(row[name]).strip()
    return ""


def main():
    tickets_path  = "tickets.csv"
    managers_path = "managers.csv"
    units_path    = "business_units.csv"
    out_dir       = "out"
    out_path      = os.path.join(out_dir, "assignments.csv")

    tickets_df  = pd.read_csv(tickets_path)
    managers_df = pd.read_csv(managers_path)
    units_df    = pd.read_csv(units_path)

    # Нормализуем заголовки — убираем пробелы, приводим к нижнему регистру
    tickets_df.columns = (
        tickets_df.columns
        .str.strip()
        .str.lower()
        .str.replace("ё", "е")
    )

    enricher = TicketEnricher()
    enriched_rows = []

    for _, row in tickets_df.iterrows():
        # После нормализации "Описание " → "описание" (без пробела)
        description = pick_value(
            row,
            "описание",          # ← после нормализации
            "description",
            "текст обращения",
        )

        city = pick_value(
            row,
            "населенный пункт",  # ← после нормализации ё→е
            "населённый пункт",
            "city",
            "город",
        )

        segment = pick_value(
            row,
            "сегмент клиента",
            "segment",
            "сегмент",
        )

        try:
            ai_data = enricher.enrich({
                "text":    description,
                "city":    city,
                "segment": segment,
            })
        except Exception as e:
            print(f"[WARN] enrich failed for guid={row.get('guid клиента', '?')}: {e}")
            ai_data = {
                "ai_type": "Консультация", "ai_lang": "RU",
                "sentiment": "NEU", "priority": 5,
                "summary": "", "recommendation": "",
                "lat": None, "lon": None,
            }

        merged = row.to_dict()
        merged.update(ai_data)
        enriched_rows.append(merged)

    enriched_df = pd.DataFrame(enriched_rows)

    engine = FIREEngine(enriched_df, managers_df, units_df)
    result_df = engine.distribute()

    os.makedirs(out_dir, exist_ok=True)
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\nOK: saved -> {out_path}\n")
    print(result_df[['guid','ai_type','ai_lang','sentiment','priority','office','manager']].head(10).to_string(index=False))
    print(f"\nВсего: {len(result_df)} | Эскалаций: {(result_df['manager'] == 'CAPITAL_ESCALATION').sum()}")


if __name__ == "__main__":
    main()