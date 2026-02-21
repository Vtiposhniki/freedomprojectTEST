# ai/llm_analyzer.py
import os
import json
import re
from ai.llm_client import get_client

MODEL_NAME = os.getenv("LLM_MODEL", "qwen/qwen3-next-80b-a3b-instruct") \
    if __import__("os").getenv("LLM_MODEL") else "qwen/qwen3-next-80b-a3b-instruct"

SYSTEM_PROMPT = """
Ты — модуль анализа обращений.

Верни СТРОГО JSON:

{
  "ai_type": "...",
  "sentiment": "POS|NEU|NEG",
  "priority": 1-10,
  "ai_lang": "RU|ENG|KZ",
  "summary": "...",
  "recommendation": "...",
  "geo": {
    "city": "...",
    "country": "...",
    "raw_address": "..."
  }
}

Допустимые ai_type:
Жалоба, Смена данных, Консультация,
Претензия, Неработоспособность приложения,
Мошеннические действия, Спам

Никакого текста вне JSON.
"""

_VALID_TYPES = {
    "Жалоба", "Смена данных", "Консультация",
    "Претензия", "Неработоспособность приложения",
    "Мошеннические действия", "Спам",
}
_VALID_SENTIMENTS = {"POS", "NEU", "NEG"}
_VALID_LANGS = {"RU", "ENG", "KZ"}


def _extract_json(text: str) -> str:
    """Вытащить JSON из ответа модели, даже если он обёрнут в ```json ... ```"""
    text = text.strip()
    # убрать markdown-блок
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        return match.group(1).strip()
    # найти первый { ... }
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        return match.group(0)
    return text


def _validate(data: dict) -> bool:
    """Базовая проверка структуры ответа."""
    if not isinstance(data, dict):
        return False
    if data.get("ai_type") not in _VALID_TYPES:
        return False
    if data.get("sentiment") not in _VALID_SENTIMENTS:
        return False
    if data.get("ai_lang") not in _VALID_LANGS:
        return False
    priority = data.get("priority")
    if not isinstance(priority, (int, float)) or not (1 <= int(priority) <= 10):
        return False
    return True


def analyze_with_llm(text: str):
    """
    Отправить текст тикета в LLM и вернуть структурированный dict.
    При любой ошибке возвращает None — вызывающий код переключится на rule-based NLP.
    """
    if not text or not text.strip():
        return None

    client = get_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text[:3000]},  # обрезаем слишком длинные тексты
            ],
            temperature=0.2,
            max_tokens=400,
            timeout=15,  # не ждём бесконечно
        )

        raw = response.choices[0].message.content or ""
        print(f"[LLM] used: {MODEL_NAME} | chars: {len(raw)}")

        json_str = _extract_json(raw)
        data = json.loads(json_str)

        if not _validate(data):
            print(f"[LLM] Invalid response structure, falling back. Got: {data}")
            return None

        # нормализуем priority в int
        data["priority"] = int(data["priority"])
        return data

    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"[LLM] Error: {type(e).__name__}: {e}")
        return None