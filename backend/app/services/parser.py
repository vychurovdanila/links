"""Парсер выгрузки Telegram Desktop (result.json) и наполнение БД.

Скрипт читает JSON-экспорт чатов Telegram, берёт по 100 последних сообщений
из каждой личной переписки, а также контакты, которых не было в чатах,
и сохраняет всё в БД через переданную SQLAlchemy-сессию.

Запуск — отдельным скриптом (см. seed.py), а не на старте приложения.
"""

import json
import os
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Group, Message, Person

# ID владельца выгрузки (числовая часть from_id вида "user708435728").
MY_TELEGRAM_ID = 708435728

# Сколько последних сообщений на чат сохраняем.
MESSAGES_LIMIT = 100

# Максимальная длина телефона в модели Person.phone_number (String(32)).
PHONE_MAX_LENGTH = 32


def _extract_telegram_id(from_id: Any) -> int | None:
    """Приводит from_id к целочисленному telegram_id.

    В выгрузке from_id имеет вид "user708435728" (строка) либо уже число.
    """
    if from_id is None:
        return None
    if isinstance(from_id, int):
        return from_id
    digits = "".join(ch for ch in str(from_id) if ch.isdigit())
    return int(digits) if digits else None


def _message_text_to_str(text_raw: Any) -> str:
    """Склеивает составной текст сообщения (строки, диктовки, ссылки) в одну строку."""
    if isinstance(text_raw, list):
        parts: list[str] = []
        for item in text_raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    if text_raw is None:
        return ""
    return str(text_raw)


def _parse_message_date(date_raw: Any) -> datetime | None:
    """Парсит дату сообщения из ISO-строки; при неверном формате вернёт None."""
    if not date_raw:
        return None
    try:
        return datetime.fromisoformat(str(date_raw))
    except ValueError:
        return None


def _iter_message_texts(msgs: list[dict[str, Any]]) -> list[str]:
    """Готовит список текстов для пакетной проверки дублей."""
    texts: list[str] = []
    for m in msgs:
        if m.get("type") != "message":
            continue
        text_str = _message_text_to_str(m.get("text", "")).strip()
        if text_str:
            texts.append(text_str)
    return texts


def parse_and_seed(db: Session) -> str:
    """Читает ../result.json и наполняет БД, возвращая текстовый отчёт."""
    # Путь к result.json (лежит в корне проекта, на уровень выше backend):
    # <корень_проекта>/result.json
    json_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "result.json")
    )

    if not os.path.exists(json_path):
        return "Ошибка: файл result.json не найден по пути " + json_path

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Группа по умолчанию для импортированных контактов.
    default_group = db.query(Group).filter(Group.name == "Входящие").first()
    if not default_group:
        default_group = Group(name="Входящие")
        db.add(default_group)
        db.flush()

    persons_added = 0
    messages_added = 0

    # 1. Личные чаты: последние MESSAGES_LIMIT сообщений на чат.
    chats = data.get("chats", {}).get("list", [])
    for chat in chats:
        if chat.get("type") != "personal_chat":
            continue

        telegram_id = _extract_telegram_id(chat.get("id"))
        if telegram_id is None:
            continue

        name = (chat.get("name") or "Без имени").strip() or "Без имени"

        person = db.query(Person).filter(Person.telegram_id == telegram_id).first()
        if not person:
            person = Person(telegram_id=telegram_id, first_name=name)
            person.groups.append(default_group)
            db.add(person)
            db.flush()
            persons_added += 1

        msgs = chat.get("messages", [])[-MESSAGES_LIMIT:]

        # Пакетная проверка уже сохранённых сообщений (защита от повторного запуска).
        existing_texts = {
            row[0]
            for row in db.query(Message.text)
            .filter(
                Message.person_id == person.id,
                Message.text.in_(_iter_message_texts(msgs)),
            )
            .all()
        }

        for m in msgs:
            if m.get("type") != "message":
                continue

            text_str = _message_text_to_str(m.get("text", "")).strip()
            if not text_str or text_str in existing_texts:
                continue

            date_value = _parse_message_date(m.get("date"))
            if date_value is None:
                continue

            db.add(
                Message(
                    person_id=person.id,
                    text=text_str,
                    date=date_value,
                    is_from_me=_extract_telegram_id(m.get("from_id"))
                    == MY_TELEGRAM_ID,
                )
            )
            existing_texts.add(text_str)
            messages_added += 1

        db.flush()

    db.commit()

    # 2. Контакты, которых не было среди личных чатов (совпадение по телефону).
    contacts = data.get("contacts", {}).get("list", [])
    for c in contacts:
        phone = (c.get("phone_number") or "").strip()
        if not phone or len(phone) > PHONE_MAX_LENGTH:
            continue

        exists = db.query(Person).filter(Person.phone_number == phone).first()
        if exists:
            continue

        full_name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        if not full_name:
            continue

        person = Person(first_name=full_name, phone_number=phone)
        person.groups.append(default_group)
        db.add(person)
        persons_added += 1

    db.commit()

    return (
        f"✅ Успешно! Загружено новых контактов: {persons_added}, "
        f"сообщений: {messages_added}"
    )
