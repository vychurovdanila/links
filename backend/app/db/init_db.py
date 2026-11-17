"""Локальная инициализация схемы БД.

Запуск: python -m app.db.init_db
Создаёт все таблицы из моделей в базе, указанной в DATABASE_URL.
Для продакшена используем Alembic, этот скрипт — только для dev.
"""

from app.db.database import Base, engine
from app.models import models  # noqa: F401  # регистрирует модели в metadata


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print("Схема БД создана:", engine.url)


if __name__ == "__main__":
    init_db()
