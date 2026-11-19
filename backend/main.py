"""Точка входа FastAPI-приложения links.

Схема БД создаётся отдельным скриптом (app/db/init_db.py), а не на старте
приложения — это требование стандарта Makefab (миграции отдельно от рантайма).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.core.config import settings
from app.db import database  # noqa: F401  # engine/Base для миграций (init_db)

app = FastAPI(title=settings.PROJECT_NAME)

# CORS: только dev-источник Vite, без wildcard'ов и без credentials
# (аутентификация будет через Bearer-токены в заголовках).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Проверка живости сервиса."""
    return {"status": "ok"}


# Роутеры домена (граф и прочее).
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
