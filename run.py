# run.py
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
    # Явная проверка ключа ДО всего остального
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key:
        print(f"[LLM] Режим: LLM (ключ найден)")
    else:
        print(f"[LLM] Режим: rule-based (ключ не найден, LLM отключён)")

    print("Читаем данные из БД...")
    tickets_df  = get_tickets_df()
    managers_df = get_managers_df()
    units_df    = get_offices_df()

    print(f"  Тикетов:    {len(tickets_df)}")
    print(f"  Менеджеров: {len(managers_df)}")
    print(f"  Офисов:     {len(units_df)}\n")

    enricher = TicketEnricher()
    enriched_rows = []

    print(f"Запускаем AI-обогащение ({len(tickets_df)} тикетов)...")
    for i, (_, row) in enumerate(tickets_df.iterrows(), 1):
        try:
            ai_data = enricher.enrich({
                "text":    pick_value(row, "description"),
                "city":    pick_value(row, "city"),
                "segment": pick_value(row, "segment"),
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

        if i % 5 == 0 or i == len(tickets_df):
            print(f"  Обогащено: {i}/{len(tickets_df)}")

    enriched_df = pd.DataFrame(enriched_rows)

    print("\nЗапускаем маршрутизацию...")
    engine = FIREEngine(enriched_df, managers_df, units_df)
    result_df = engine.distribute()

    save_results(result_df)

    escalations = (result_df["manager"] == "CAPITAL_ESCALATION").sum()
    print(f"\nГотово! Всего: {len(result_df)} | Эскалаций: {escalations}")
    print(result_df[["guid","ai_type","sentiment","priority","office","manager"]].to_string(index=False))


if __name__ == "__main__":
    main()