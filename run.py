# run.py
import os
import pandas as pd

from engine import FIREEngine
from ai.enricher import TicketEnricher


# ------------------------------------------------------------
# Helper: safe column extractor
# ------------------------------------------------------------

def pick_value(row, *possible_names):
    """
    Return first existing non-null column value from row.
    """
    for name in possible_names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return ""


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():

    tickets_path = "tickets.csv"
    managers_path = "managers.csv"
    units_path = "business_units.csv"

    out_dir = "out"
    out_path = os.path.join(out_dir, "assignments.csv")

    # -----------------------------
    # Load CSV
    # -----------------------------

    tickets_df = pd.read_csv(tickets_path)
    managers_df = pd.read_csv(managers_path)
    units_df = pd.read_csv(units_path)

    # normalize column names early (lowercase)
    tickets_df.columns = (
        tickets_df.columns
        .str.strip()
        .str.lower()
        .str.replace("ё", "е")
    )

    # -----------------------------
    # AI ENRICHMENT
    # -----------------------------

    enricher = TicketEnricher()
    enriched_rows = []

    for _, row in tickets_df.iterrows():

        description = pick_value(
            row,
            "description",
            "описание",
            "текст обращения"
        )

        city = pick_value(
            row,
            "city",
            "город",
            "населенный пункт"
        )

        segment = pick_value(
            row,
            "segment",
            "сегмент",
            "сегмент клиента"
        )

        base_ticket = {
            "text": description,
            "city": city,
            "segment": segment,
        }

        ai_data = enricher.enrich(base_ticket)

        merged = row.to_dict()
        merged.update(ai_data)

        enriched_rows.append(merged)

    enriched_df = pd.DataFrame(enriched_rows)

    # -----------------------------
    # ROUTING
    # -----------------------------

    engine = FIREEngine(enriched_df, managers_df, units_df)
    result_df = engine.distribute()

    # -----------------------------
    # SAVE
    # -----------------------------

    os.makedirs(out_dir, exist_ok=True)
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\nOK: saved -> {out_path}\n")
    print(result_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()