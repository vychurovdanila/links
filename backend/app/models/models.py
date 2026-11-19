"""ORM-модели домена links.

Структура:
- Person   — человек (контакт из Telegram).
- Group    — слой/группа (Работа, Семья, Песочница).
- Agreement — договорённость, привязанная к человеку.
- Message  — сообщение из переписки с человеком.
Связь Person <-> Group реализована через ассоциативную таблицу person_groups.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

# Ассоциативная таблица «многие-ко-многим»: person <-> group.
person_groups = Table(
    "person_groups",
    Base.metadata,
    Column(
        "person_id",
        Integer,
        ForeignKey("persons.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "group_id",
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Person(Base):
    """Контакт (человек)."""

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int | None] = mapped_column(
        Integer, unique=True, index=True, nullable=True
    )
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Связи
    groups: Mapped[list["Group"]] = relationship(
        secondary=person_groups,
        back_populates="persons",
    )
    agreements: Mapped[list["Agreement"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return f"<Person id={self.id} name={self.first_name!r}>"


class Group(Base):
    """Группа (слой) контактов."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    is_sandbox: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )

    # Связи
    persons: Mapped[list["Person"]] = relationship(
        secondary=person_groups,
        back_populates="groups",
    )

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return f"<Group id={self.id} name={self.name!r}>"


class Agreement(Base):
    """Договорённость с человеком и её дедлайн."""

    __tablename__ = "agreements"
    # Защита от накопления дублей: у одного человека текст договорённости уникален.
    __table_args__ = (
        UniqueConstraint("person_id", "text", name="_person_agreement_uc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Название кейса (дела/проекта), к которому относится договорённость.
    # Заполняется ИИ; может отсутствовать.
    case_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Тип договорённости: commitment / intention / closed.
    type: Mapped[str] = mapped_column(
        String(32), default="commitment", nullable=False, server_default="commitment"
    )
    # Кто должен выполнить: me (я) или them (собеседник).
    debtor: Mapped[str] = mapped_column(
        String(16), default="me", nullable=False, server_default="me"
    )
    # Примерная ли дата (например, «на днях», «в течение месяца»).
    is_approximate: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False
    )

    # Связи
    person: Mapped["Person"] = relationship(back_populates="agreements")

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return f"<Agreement id={self.id} person_id={self.person_id}>"


class Message(Base):
    """Сообщение из переписки с человеком."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("person_id", "date", "text", name="uq_message_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_from_me: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )

    # Связи
    person: Mapped["Person"] = relationship(back_populates="messages")

    def __repr__(self) -> str:  # pragma: no cover - отладка
        return f"<Message id={self.id} person_id={self.person_id}>"
