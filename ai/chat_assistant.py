# ai/chat_assistant.py
"""
AI-ассистент для аналитики дашборда.
Умеет отвечать на вопросы по данным из БД через LLM или rule-based fallback.
"""

import json
import requests
from typing import Optional


API_BASE = "http://localhost:8000"


def ask(question: str, history: list = []) -> dict:
    """
    Отправить вопрос AI-ассистенту.
    
    Args:
        question: Вопрос на русском языке
        history:  Список предыдущих сообщений [{"role": "user/assistant", "content": "..."}]
    
    Returns:
        {"answer": str, "source": "llm"|"fallback"}
    """
    try:
        resp = requests.post(
            f"{API_BASE}/ai/chat",
            json={"question": question, "history": history},
            timeout=25,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {
            "answer": "⚠️ API сервер недоступен. Запустите: `uvicorn api:app --reload`",
            "source": "error",
        }
    except Exception as e:
        return {
            "answer": f"⚠️ Ошибка: {e}",
            "source": "error",
        }


# Примеры вопросов для UI
SUGGESTED_QUESTIONS = [
    "Сколько всего тикетов и какой процент эскалаций?",
    "Какой офис обрабатывает больше всего обращений?",
    "Какие типы обращений встречаются чаще всего?",
    "Кто из менеджеров перегружен больше всего?",
    "Сколько тикетов с негативным сентиментом?",
    "Какой средний приоритет у тикетов типа Жалоба?",
    "В каком офисе больше всего эскалаций?",
    "Есть ли проблемы с распределением нагрузки?",
]
