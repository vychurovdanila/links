"""Раннер импорта данных из выгрузки Telegram в БД links.

Запуск: python seed.py  (из каталога backend)
Скрипт читает result.json и наполняет links.db. Схему БД создаёт отдельно
app/db/init_db.py — seed только наполняет уже созданные таблицы.
"""

from app.db.database import SessionLocal
from app.services.parser import parse_and_seed


def main() -> None:
    db = SessionLocal()
    try:
        result = parse_and_seed(db)
        print(result)
    except Exception as e:  # noqa: BLE001  # верхнеуровневый отчёт об ошибке
        print(f"❌ Ошибка при парсинге: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
