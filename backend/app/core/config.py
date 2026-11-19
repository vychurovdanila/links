"""Настройки приложения.

Чтение конфигурации из переменных окружения / файла .env.
Пароль и строки подключения не хардкодятся в коде: приложение падает
на старте, если обязательная переменная (DATABASE_URL) не задана.
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень бэкенда: .../backend (используется, чтобы .env читался
# независимо от текущей рабочей директории процесса).
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Конфигурация бэкенда links."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Обязательная переменная: приложение не запустится без неё.
    DATABASE_URL: str

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_sqlite_path(cls, value: str) -> str:
        """Превращает относительный путь SQLite в абсолютный (относительно backend).

        Это гарантирует, что links.db всегда создаётся в каталоге backend,
        независимо от текущей рабочей директории запущенного процесса.
        """
        prefix = "sqlite:///"
        if value.startswith(prefix):
            db_path = value[len(prefix):]
            # Абсолютные пути (Windows: "C:/..." или "D:/...") не трогаем.
            if not Path(db_path).is_absolute():
                absolute = (BASE_DIR / db_path).resolve()
                return f"{prefix}{absolute.as_posix()}"
        return value

    # Разрешённые источники фронтенда (Vite dev-сервер):
    # localhost — для работы за тем же ПК, LAN-адреса — для доступа с телефона.
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.0.111:5173",
        "http://192.168.0.111:8000",
    ]

    # Название проекта (для заголовков и документации).
    PROJECT_NAME: str = "Links API"


settings = Settings()
