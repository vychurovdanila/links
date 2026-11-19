"""Сервис интеграции с GigaChat API для извлечения договорённостей.

Берёт текст переписки с одним человеком, отправляет его в GigaChat
и просит вернуть список договорённостей в формате JSON.

Ключ авторизации (GIGACHAT_AUTH_KEY) читается из переменных окружения /
файла .env и в коде не хардкодится.
"""

import json
import os
import uuid

import requests
from dotenv import load_dotenv

load_dotenv()

# Ключ авторизации GigaChat (Basic-токен). Задаётся в .env.
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")

# Адреса API GigaChat.
OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

# Таймаут HTTP-запросов (секунды), чтобы скрипт не зависал бесконечно.
REQUEST_TIMEOUT = 60


def get_gigachat_token() -> str:
    """Получает временный access_token для GigaChat."""
    if not GIGACHAT_AUTH_KEY:
        raise Exception(
            "Переменная окружения GIGACHAT_AUTH_KEY не задана — "
            "добавьте её в .env"
        )

    payload = "scope=GIGACHAT_API_PERS"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {GIGACHAT_AUTH_KEY}",
    }
    response = requests.post(
        OAUTH_URL,
        headers=headers,
        data=payload,
        verify=False,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise Exception(f"Ошибка авторизации GigaChat: {response.text}")
    return response.json()["access_token"]


def _parse_agreements_json(content: str) -> list[dict]:
    """Извлекает JSON-массив договорённостей из ответа модели.

    GigaChat иногда оборачивает JSON в markdown-разметку (```json ... ```)
    либо добавляет пояснительный текст вокруг массива. Сначала пробуем
    распарсить строку как есть, затем — вырезать первый JSON-массив.
    """
    cleaned = content.strip().replace("```json", "").replace("```", "").strip()

    # 1. Пробуем распарсить как есть.
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2. Ищем встроенный JSON-массив (от первой '[' до последней ']').
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    print(f"Не удалось распарсить ответ ИИ: {content}")
    return []


def extract_agreements(messages_text: str) -> list[dict]:
    """Отправляет текст в GigaChat и просит найти договорённости."""
    token = get_gigachat_token()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    prompt = f"""
    Проанализируй переписку и найди все договоренности, обещания или задачи.
    Верни ТОЛЬКО JSON-массив объектов в формате: 
    [{{"text": "суть договоренности", "deadline": "YYYY-MM-DD или null"}}]
    Если договоренностей нет, верни пустой массив [].
    
    Переписка:
    {messages_text}
    """

    payload = {
        "model": "GigaChat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }

    response = requests.post(
        CHAT_URL,
        headers=headers,
        json=payload,
        verify=False,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise Exception(f"Ошибка GigaChat: {response.text}")

    content = response.json()["choices"][0]["message"]["content"]

    # Очистка от markdown-разметки и извлечение JSON-массива.
    return _parse_agreements_json(content)
