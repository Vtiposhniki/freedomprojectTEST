# ai/llm_client.py

import os

_openai_available = False
_client = None
_last_key = None  # запоминаем с каким ключом создан клиент

try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    print("[LLM] 'openai' package not installed — LLM disabled, fallback to rule-based NLP")


def get_client():
    global _client, _last_key

    if not _openai_available:
        return None

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        _client = None
        _last_key = None
        return None

    # Переиспользуем клиент если ключ не изменился
    if _client is not None and _last_key == api_key:
        return _client

    base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

    try:
        _client = OpenAI(api_key=api_key, base_url=base_url)
        _last_key = api_key
        print(f"[LLM] Client initialized → {base_url}")
        return _client
    except Exception as e:
        print(f"[LLM] Client init failed: {e}")
        return None