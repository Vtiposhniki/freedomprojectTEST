# ai/llm_client.py

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None

def get_client():
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("[LLM] OPENROUTER_API_KEY not found")
        return None

    print("[LLM] OPENROUTER_API_KEY loaded")

    _client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )

    return _client