# run.py
import os
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine import FIREEngine
from ai.enricher import TicketEnricher
from db import get_tickets_df, get_managers_df, get_offices_df, save_results

# Сколько тикетов обогащать параллельно.
# 5 — безопасно для большинства LLM API (не триггерит rate limit).
# Можно поднять до 8-10 если API не ругается.
MAX_WORKERS = 20


def enrich_one(enricher: TicketEnricher, row: pd.Series) -> dict:
    """Обогатить один тикет. Запускается в отдельном потоке."""
    t0 = time.time()
    try:
        ai_data = enricher.enrich({
            "text":    str(row.get("description", "") or ""),
            "city":    str(row.get("city", "") or ""),
            "segment": str(row.get("segment", "") or ""),
        })
    except Exception as e:
        print(f"[WARN] enrich failed for {row.get('guid')}: {e}")
        ai_data = {
            "ai_type": "Консультация", "ai_lang": "RU",
            "sentiment": "NEU", "priority": 5,
            "summary": "", "recommendation": "",
            "lat": None, "lon": None,
        }

    elapsed = time.time() - t0
    if elapsed > 10:
        print(f"  [SLOW] guid={row.get('guid')} — {elapsed:.1f}s (превышен лимит 10с)")

    merged = row.to_dict()
    merged.update(ai_data)
    return merged


def main():
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key:
        print(f"[LLM] Режим: LLM (ключ найден) | параллельность: {MAX_WORKERS} потоков")
    else:
        print(f"[LLM] Режим: rule-based (ключ не найден)")

    print("Читаем данные из БД...")
    tickets_df  = get_tickets_df()
    managers_df = get_managers_df()
    units_df    = get_offices_df()

    print(f"  Тикетов:    {len(tickets_df)}")
    print(f"  Менеджеров: {len(managers_df)}")
    print(f"  Офисов:     {len(units_df)}\n")

    enricher = TicketEnricher()
    enriched_rows = [None] * len(tickets_df)  # список фиксированного размера — сохраняем порядок
    rows_list = [(i, row) for i, (_, row) in enumerate(tickets_df.iterrows())]

    print(f"Запускаем AI-обогащение ({len(tickets_df)} тикетов, {MAX_WORKERS} потоков)...")
    t_enrich_start = time.time()
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Запускаем все задачи сразу
        future_to_idx = {
            executor.submit(enrich_one, enricher, row): idx
            for idx, row in rows_list
        }

        # Собираем результаты по мере готовности
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            enriched_rows[idx] = future.result()
            done += 1
            if done % 5 == 0 or done == len(tickets_df):
                elapsed = time.time() - t_enrich_start
                print(f"  Обогащено: {done}/{len(tickets_df)} | {elapsed:.1f}s итого")

    total_enrich_time = time.time() - t_enrich_start
    enriched_df = pd.DataFrame(enriched_rows)

    print("\nЗапускаем маршрутизацию...")
    t_routing = time.time()
    engine = FIREEngine(enriched_df, managers_df, units_df)
    result_df = engine.distribute()
    routing_elapsed = time.time() - t_routing

    save_results(result_df)

    escalations = (result_df["manager"] == "CAPITAL_ESCALATION").sum()

    print(f"\n{'='*55}")
    print(f"  Всего тикетов:        {len(result_df)}")
    print(f"  Эскалаций:            {escalations}")
    print(f"  Время обогащения:     {total_enrich_time:.1f}s (было ~64s)")
    print(f"  Время маршрутизации:  {routing_elapsed:.3f}s")
    print(f"{'='*55}\n")

    print(result_df[["guid", "ai_type", "sentiment", "priority", "office", "manager"]].to_string(index=False))


if __name__ == "__main__":
    main()