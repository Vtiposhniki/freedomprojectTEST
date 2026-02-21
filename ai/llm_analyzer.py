# ai/llm_analyzer.py

import json
from ai.llm_client import get_client

MODEL_NAME = "qwen/qwen3-next-80b-a3b-instruct"

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

def analyze_with_llm(text: str):
    client = get_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.2,
            max_tokens=350
        )

        print("[LLM] used:", MODEL_NAME)

        content = response.choices[0].message.content.strip()

        # если модель вернула ```json ... ```
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1].strip()
                if content.lower().startswith("json"):
                    content = content[4:].strip()

        return json.loads(content)

    except Exception as e:
        print("LLM error:", e)
        return None