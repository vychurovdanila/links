"""Подключение к базе данных: engine, сессии и декларативная база.

Миграции выполняются отдельно (см. app/db/init_db.py), а не на старте
приложения — это требование стандарта Makefab.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# SQLite требует отключения проверки потока при использовании с FastAPI.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


def get_db():
    """FastAPI-зависимость: выдаёт сессию и гарантированно закрывает её."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
