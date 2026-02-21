# run.py
"""
Основной скрипт запуска FIRE Engine.
Читает данные из PostgreSQL (не из CSV).
Записывает результат обратно в PostgreSQL.
"""

import os
import pandas as pd
from engine import FIREEngine
from ai.enricher import TicketEnricher
from db import get_tickets_df, get_managers_df, get_offices_df, save_results


def pick_value(row, *possible_names):
    for name in possible_names:
        if name in row and pd.notna(row[name]) and str(row[name]).strip():
            return str(row[name]).strip()
    return ""


def main():
    print("Читаем данные из БД...")
    tickets_df  = get_tickets_df()
    managers_df = get_managers_df()
    units_df    = get_offices_df()

    print(f"  Тикетов:   {len(tickets_df)}")
    print(f"  Менеджеров:{len(managers_df)}")
    print(f"  Офисов:    {len(units_df)}\n")

    # --- AI обогащение ---
    enricher = TicketEnricher()
    enriched_rows = []

    for _, row in tickets_df.iterrows():
        description = pick_value(row, "description")
        city        = pick_value(row, "city")
        segment     = pick_value(row, "segment")

        try:
            ai_data = enricher.enrich({
                "text":    description,
                "city":    city,
                "segment": segment,
            })
        except Exception as e:
            print(f"[WARN] enrich failed for {row.get('guid')}: {e}")
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

    # --- Маршрутизация ---
    print("Запускаем маршрутизацию...")
    engine = FIREEngine(enriched_df, managers_df, units_df)
    result_df = engine.distribute()

    # --- Сохранить результат в БД ---
    save_results(result_df)

    # --- Итог ---
    escalations = (result_df["manager"] == "CAPITAL_ESCALATION").sum()
    print(f"\nГотово! Всего: {len(result_df)} | Эскалаций: {escalations}")
    print(result_df[["guid","ai_type","sentiment","priority","office","manager"]].to_string(index=False))


if __name__ == "__main__":
    main()