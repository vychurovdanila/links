"""Сервис интеграции с GigaChat API для извлечения договорённостей.

Берёт текст переписки с одним человеком, отправляет его в GigaChat
и просит вернуть список договорённостей в формате JSON.

Ключ авторизации (GIGACHAT_AUTH_KEY) читается из переменных окружения /
файла .env и в коде не хардкодится.
"""

import json
import os
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher

import requests
from dotenv import load_dotenv

load_dotenv()

# Регулярка для даты дедлайна: строго YYYY-MM-DD (с необязательным временем).
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

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


def _clean_deadline(value: object) -> str | None:
    """Нормализует дедлайн из ответа модели.

    GigaChat часто возвращает текстовые заглушки вместо даты: «нет срока»,
    «null», «today», «after_meeting». Оставляем только то, что похоже на
    дату формата YYYY-MM-DD; всё остальное приводим к None, чтобы в БД не
    попадал мусор.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Оставляем только даты формата YYYY-MM-DD (допускаем ISO с временем).
    if _DATE_RE.match(text):
        return text[:10]
    return None


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
            return _normalize_agreements(parsed)
    except json.JSONDecodeError:
        pass

    # 2. Ищем встроенный JSON-массив (от первой '[' до последней ']').
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, list):
                return _normalize_agreements(parsed)
        except json.JSONDecodeError:
            pass

    print(f"Не удалось распарсить ответ ИИ: {content}")
    return []


def _normalize_key(text: str) -> str:
    """Ключ для дедупликации: нижний регистр, без пунктуации и лишних пробелов.

    GigaChat при повторном анализе формулирует одну и ту же задачу чуть
    иначе (точка в конце, другой регистр, иной порядок слов вокруг знаков
    препинания). Точное сравнение строк такие повторы не ловит, поэтому
    сравниваем по «очищенному» тексту.
    """
    return re.sub(r"[\W_]+", " ", text.lower(), flags=re.UNICODE).strip()


# Порог схожести для нечёткой дедупликации. Замеры на реальных данных:
#   * истинные перефразы одной задачи — 0.98–1.00;
#   * разные задачи, но похожие по формулировке — 0.79–0.86
#     («Отправить посылку» vs «Забрать посылку» = 0.86,
#      «Созвониться в четверг вечером» vs «в пятницу вечером» = 0.79).
# Порог 0.90 лежит между этими группами: отсекает явные повторы и НЕ
# склеивает разные задачи. Внешние зависимости не используем — только difflib.
FUZZY_DUP_THRESHOLD = 0.90


def _is_duplicate(text: str, existing_keys: set[str], threshold: float = FUZZY_DUP_THRESHOLD) -> bool:
    """Проверяет, есть ли уже такая договорённость среди сохранённых.

    Две ступени: точное совпадение нормализованного текста → нечёткое сходство
    (difflib.SequenceMatcher). Так ловятся близкие перефразы одной задачи,
    которые ИИ выдаёт при повторном анализе той же переписки.

    Важно: правило «подстрока в подстроке» сознательно НЕ используется —
    оно ошибочно схлопывало разные задачи («Созвониться в четверг» ⊂
    «Созвониться в четверг вечером»). Порог подобран так, чтобы разные
    задачи («Отправить посылку» vs «Забрать посылку», ratio 0.86) не
    склеивались, а перефразы (ratio ≥ 0.98) — отсекались.
    """
    key = _normalize_key(text)
    if not key:
        return True
    if key in existing_keys:
        return True
    for existing in existing_keys:
        if not existing:
            continue
        if SequenceMatcher(None, key, existing).ratio() >= threshold:
            return True
    return False


def _normalize_agreements(items: list) -> list[dict]:
    """Чистит список договорённостей: нормализует поля и отбрасывает мусор.

    Помимо очистки дедлайна убираем записи без текста и дубли внутри
    одного ответа модели — чтобы в БД не накапливались повторы.
    Значения type/debtor приводим к допустимым, иначе ставим дефолт.
    """
    result: list[dict] = []
    seen_keys: set[str] = set()
    # Типы по 4 квадрантам: договорённость, просьба, намерение.
    # "ignore" и любые неизвестные значения приводим к "intention".
    valid_types = {"agreement", "request", "intention"}
    valid_debtors = {"me", "them"}

    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        # Отбрасываем повторы внутри одного ответа модели (в т.ч. перефразы).
        if _is_duplicate(text, seen_keys):
            continue
        seen_keys.add(_normalize_key(text))

        ag_type = str(item.get("type") or "intention").strip().lower()
        if ag_type not in valid_types:
            ag_type = "intention"

        debtor = str(item.get("debtor") or "me").strip().lower()
        if debtor not in valid_debtors:
            debtor = "me"

        case_name = item.get("case_name")
        case_name = str(case_name).strip() if case_name else None

        result.append(
            {
                "text": text,
                "case_name": case_name or None,
                "type": ag_type,
                "debtor": debtor,
                "deadline": _clean_deadline(item.get("deadline")),
                "is_approximate": bool(item.get("is_approximate", False)),
            }
        )
    return result


def extract_agreements(messages_text: str) -> list[dict]:
    """Отправляет текст в GigaChat и просит найти договорённости."""
    token = get_gigachat_token()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Сегодняшняя дата передаётся в промпт, чтобы модель могла посчитать
    # относительные сроки ("завтра", "в четверг") в конкретную дату.
    # (дата подставляется прямо в f-строку промпта ниже)

    prompt = f"""
    Ты — умный AI-ассистент CRM. Проанализируй переписку. 
    Сегодняшняя дата: {datetime.now().strftime('%Y-%m-%d')}.

    Классифицируй каждую найденную сущность по типу (type) и определи, на чьей стороне мяч (debtor):
    1. "agreement" (Договоренность) — есть явное согласие обеих сторон. debtor="me" (если я обещал), debtor="them" (если они обещали).
    2. "request" (Просьба) — один просит другого, но НЕТ четкого согласия. debtor="me" (если ОНИ просят МЕНЯ), debtor="them" (если Я прошу ИХ).
    3. "intention" (Намерение) — планы без обязательств ("надо бы встретиться").
    4. "ignore" — личные дела собеседника ("я поеду смотреть квартиру"), НЕ сохраняй их.

    ВАЖНО: Статус "closed" (выполнено) можно ставить ТОЛЬКО если есть явное
    подтверждение завершения (например: "Спасибо, получил", "Оплатил", "Сделано",
    "Вопрос решен"). Если собеседник говорит "я вернусь через пару дней" или
    "я посмотрю", это НЕ закрытая задача, а активная договоренность (agreement)
    или просьба (request) с дедлайном.

    Верни ТОЛЬКО валидный JSON-массив:
    [
      {{
        "type": "agreement" | "request" | "intention",
        "case_name": "краткое название темы",
        "text": "суть задачи",
        "debtor": "me" | "them",
        "deadline": "YYYY-MM-DD" (или null),
        "is_approximate": true | false
      }}
    ]
    Если ничего нет, верни [].

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
