"""Тестовый скрипт: извлекает договорённости из переписки через GigaChat.

Запускается отдельно от приложения: python test_ai.py
"""

import sys
import time
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.models.models import Agreement, Message, Person
from app.services.ai_service import _is_duplicate, _normalize_key, extract_agreements

# Сколько человек проверяем за один прогон и сколько сообщений отправляем в ИИ.
PERSONS_LIMIT = 5
MESSAGES_LIMIT = 1000
# Минимальное количество сообщений, чтобы у ИИ был осмысленный контекст.
MIN_MESSAGES = 100
# Пауза между запросами к GigaChat, чтобы не превысить лимиты API (секунды).
REQUEST_DELAY = 2

# Консоль Windows по умолчанию использует cp1251 и падает на эмодзи.
# Принудительно переключаем stdout на UTF-8, чтобы скрипт не падал.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def _parse_deadline(value) -> datetime | None:
    """Парсит дедлайн из строки; при ошибке вернёт None.

    Поддерживает как "YYYY-MM-DD", так и ISO-формат с временем
    ("YYYY-MM-DDTHH:MM"), который иногда возвращает GigaChat.
    """
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _load_persons(db) -> list[tuple[Person, int]]:
    """Возвращает 5 случайных человек, у которых больше MIN_MESSAGES сообщений.

    Считаем сообщения отдельным запросом с GROUP BY/HAVING: так фильтр
    «больше N сообщений» применяется на стороне БД, а не после загрузки
    всех людей в память. func.random() — случайная сортировка в SQLite.
    """
    counts = (
        db.query(Message.person_id, func.count(Message.id).label("messages_count"))
        .group_by(Message.person_id)
        .having(func.count(Message.id) > MIN_MESSAGES)
        .subquery()
    )

    rows = (
        db.query(Person, counts.c.messages_count)
        .join(counts, Person.id == counts.c.person_id)
        .order_by(func.random())
        .limit(PERSONS_LIMIT)
        .all()
    )
    return [(person, int(count)) for person, count in rows]


def analyze_person(db, person: Person, messages_count: int) -> None:
    """Анализирует переписку с одним человеком через GigaChat.

    Любая ошибка (сеть, GigaChat, пустой/невалидный ответ) логируется,
    но не прерывает общий прогон по остальным людям.
    """
    print(f"\n=== {person.first_name} (сообщений: {messages_count}) ===")

    # Берем последние MESSAGES_LIMIT сообщений: свежие сначала, потом разворачиваем.
    msgs = (
        db.query(Message)
        .filter(Message.person_id == person.id)
        .order_by(Message.date.desc())
        .limit(MESSAGES_LIMIT)
        .all()
    )
    msgs.reverse()

    text_to_analyze = "\n".join(
        f"{'Я' if m.is_from_me else person.first_name}: {m.text}" for m in msgs
    )

    print(f"Отправляем запрос в GigaChat ({len(msgs)} сообщений)...")
    try:
        agreements = extract_agreements(text_to_analyze)
    except Exception as e:  # noqa: BLE001  # любая ошибка ИИ не должна ломать прогон
        print(f"❌ Ошибка GigaChat: {e}")
        return

    if not agreements:
        print("Договоренности: []")
        return

    print(f"Найдено записей: {len(agreements)}")
    for ag in agreements:
        print(
            f"- [{ag.get('type')}/{ag.get('debtor')}] {ag.get('text')} "
            f"(кейс: {ag.get('case_name')}, дедлайн: {ag.get('deadline')})"
        )

    # Уже сохранённые тексты договорённостей этого человека — для защиты от
    # накопления дублей при повторных запусках. Сравниваем по нормализованному
    # ключу (без регистра/пунктуации), т.к. ИИ перефразирует задачи чуть иначе.
    existing_keys = {
        _normalize_key(row[0])
        for row in db.query(Agreement.text)
        .filter(Agreement.person_id == person.id)
        .all()
    }

    new_count = 0
    skipped_count = 0
    for ag in agreements:
        text_value = (ag.get("text") or "").strip()
        if not text_value or _is_duplicate(text_value, existing_keys):
            skipped_count += 1
            continue

        db.add(
            Agreement(
                person_id=person.id,
                text=text_value,
                case_name=ag.get("case_name"),
                type=ag.get("type", "intention"),
                debtor=ag.get("debtor", "me"),
                is_approximate=bool(ag.get("is_approximate", False)),
                deadline=_parse_deadline(ag.get("deadline")),
                is_completed=False,
            )
        )
        existing_keys.add(_normalize_key(text_value))
        new_count += 1

    if not new_count:
        print(f"✅ Новых договоренностей нет (пропущено дублей: {skipped_count}).")
        return

    # Сохраняем в БД только когда есть что добавлять. IntegrityError ловим
    # отдельно: уникальный индекс (_person_agreement_uc) — последний барьер
    # от гонок/пропущенной дедупликации, он не должен ломать прогон.
    try:
        db.commit()
        print(f"✅ Сохранено в БД: {new_count} (пропущено дублей: {skipped_count}).")
    except IntegrityError:
        db.rollback()
        print(
            f"⚠️ Часть записей уже есть в БД (уникальный индекс). "
            f"Пропущено дублей: {skipped_count}."
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        print(f"❌ Ошибка сохранения в БД: {e}")


def test_persons() -> None:
    db = SessionLocal()
    try:
        persons = _load_persons(db)
        if not persons:
            print(f"Нет людей с числом сообщений больше {MIN_MESSAGES}")
            return

        print(f"Анализируем {len(persons)} человек(а) с расширенным контекстом.")

        for index, (person, messages_count) in enumerate(persons):
            analyze_person(db, person, messages_count)
            # Пауза между запросами к API (после последнего — не нужна).
            if index < len(persons) - 1:
                time.sleep(REQUEST_DELAY)

        print("\nГотово.")
    finally:
        db.close()


if __name__ == "__main__":
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    test_persons()
