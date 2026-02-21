# ai/llm_client.py

import os

_client = None
_openai_available = False

try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    print("[LLM] 'openai' package not installed — LLM disabled, fallback to rule-based NLP")


def get_client():
    global _client

    if not _openai_available:
        return None

    if _client is not None:
        return _client

    # Поддержка двух переменных окружения: OPENROUTER и прямой Anthropic/OpenAI
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

    if not api_key:
        print("[LLM] No API key found (OPENROUTER_API_KEY / OPENAI_API_KEY) — LLM disabled")
        return None

    try:
        _client = OpenAI(api_key=api_key, base_url=base_url)
        print(f"[LLM] Client initialized → {base_url}")
        return _client
    except Exception as e:
        print(f"[LLM] Client init failed: {e}")
        return None