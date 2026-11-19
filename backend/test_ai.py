"""Тестовый скрипт: извлекает договорённости из переписки через GigaChat.

Запускается отдельно от приложения: python test_ai.py
"""

import sys
from datetime import datetime

from app.db.database import SessionLocal
from app.models.models import Agreement, Message, Person
from app.services.ai_service import extract_agreements

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


def test_one_person() -> None:
    db = SessionLocal()
    try:
        # Берем первого человека, у которого есть сообщения
        person = db.query(Person).filter(Person.messages.any()).first()
        if not person:
            print("Нет людей с сообщениями")
            return

        print(f"Анализируем переписку с: {person.first_name}")

        # Берем последние 30 сообщений для теста (чтобы не тратить токены)
        msgs = (
            db.query(Message)
            .filter(Message.person_id == person.id)
            .order_by(Message.date.desc())
            .limit(30)
            .all()
        )
        msgs.reverse()

        text_to_analyze = "\n".join(
            f"{'Я' if m.is_from_me else person.first_name}: {m.text}" for m in msgs
        )

        print("Отправляем запрос в GigaChat...")
        agreements = extract_agreements(text_to_analyze)

        print(f"Найдено договоренностей: {len(agreements)}")
        for ag in agreements:
            print(f"- {ag.get('text')} (дедлайн: {ag.get('deadline')})")

            # Сохраняем в БД
            new_ag = Agreement(
                person_id=person.id,
                text=ag.get("text"),
                deadline=_parse_deadline(ag.get("deadline")),
                is_completed=False,
            )
            db.add(new_ag)
        db.commit()
        print("✅ Сохранено в БД.")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    test_one_person()
