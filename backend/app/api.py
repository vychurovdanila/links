"""HTTP-эндпоинты домена links.

Здесь собраны роутеры, которые подключаются к приложению в main.py.
Данные для графа отдаются в формате, совместимом с React Flow:
{"nodes": [...], "edges": [...]}.
"""

import random

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Agreement, Person

router = APIRouter(prefix="/api", tags=["graph"])

# Максимум людей в одном ответе графа (защита браузера от тысяч узлов).
# Пагинация появится позже — пока отдаём первые N контактов с Telegram.
GRAPH_PERSONS_LIMIT = 50

# Радиус разброса случайных позиций узлов вокруг центра (в пикселях React Flow).
GRAPH_SPREAD = 400

# Статусы договорённости, которые считаются «закрытыми» и не влияют на цвет узла.
CLOSED_TYPES = {"closed"}

# Стили узлов по квадрантам (совместимы с React Flow: стили задаются инлайном).
# Приоритет при нескольких открытых делах: долг важнее просьбы.
#   красный    — незакрытый agreement с debtor="me"  (мой долг);
#   синий      — незакрытый agreement с debtor="them" (их долг);
#   фиолетовый — незакрытый request с debtor="me"    (их просьба ко мне);
#   оранжевый  — незакрытый request с debtor="them"  (моя просьба к ним);
#   серый      — только intention или закрытые дела.
STYLE_RED = {
    "background": "#7f1d1d",
    "border": "2px solid #ef4444",
    "color": "white",
    "borderRadius": "50%",
    "padding": "10px",
}
STYLE_BLUE = {
    "background": "#1e3a8a",
    "border": "2px solid #3b82f6",
    "color": "white",
    "borderRadius": "50%",
    "padding": "10px",
}
STYLE_PURPLE = {
    "background": "#4c1d95",
    "border": "2px solid #a855f7",
    "color": "white",
    "borderRadius": "50%",
    "padding": "10px",
}
STYLE_ORANGE = {
    "background": "#78350f",
    "border": "2px solid #f59e0b",
    "color": "white",
    "borderRadius": "50%",
    "padding": "10px",
}
STYLE_GRAY = {
    "background": "#334155",
    "color": "white",
    "borderRadius": "50%",
    "padding": "10px",
}

# Центральный узел «Я».
ME_NODE: dict = {
    "id": "me",
    "type": "default",
    "position": {"x": 0, "y": 0},
    "data": {"label": "Я"},
    "style": {
        "background": "#1e293b",
        "color": "white",
        "border": "2px solid #3b82f6",
        "borderRadius": "50%",
        "padding": "20px",
    },
}


def _is_open(agreement: Agreement) -> bool:
    """Договорённость «открыта», если не завершена и не помечена как closed."""
    if agreement.is_completed:
        return False
    return (agreement.type or "").lower() not in CLOSED_TYPES


def _serialize_agreement(agreement: Agreement) -> dict:
    """Приводит ORM-объект Agreement к простому словарю для фронтенда."""
    deadline = agreement.deadline
    return {
        "id": agreement.id,
        "text": agreement.text,
        "case_name": agreement.case_name,
        "type": agreement.type,
        "debtor": agreement.debtor,
        "is_approximate": agreement.is_approximate,
        "is_completed": agreement.is_completed,
        "deadline": deadline.strftime("%Y-%m-%d") if deadline else None,
    }


def _pick_node_style(agreements: list[Agreement]) -> dict:
    """Определяет цвет узла по 4 квадрантам дел человека.

    Приоритет при нескольких незакрытых делах: долг (agreement) важнее
    просьбы (request). Внутри одного типа «мой» (debtor="me") важнее.

    - красный    — незакрытый agreement, debtor="me"  (мой долг);
    - синий      — незакрытый agreement, debtor="them" (их долг);
    - фиолетовый — незакрытый request,   debtor="me"  (просят меня);
    - оранжевый  — незакрытый request,   debtor="them" (прошу я);
    - серый      — только intention или закрытые дела.
    """
    open_agreements = [a for a in agreements if _is_open(a)]

    def _has(ag_type: str, debtor: str) -> bool:
        return any(
            (a.type or "").lower() == ag_type and a.debtor == debtor
            for a in open_agreements
        )

    # Долги важнее просьб: сначала квадранты agreement, затем request.
    if _has("agreement", "me"):
        return STYLE_RED
    if _has("agreement", "them"):
        return STYLE_BLUE
    if _has("request", "me"):
        return STYLE_PURPLE
    if _has("request", "them"):
        return STYLE_ORANGE

    # Иначе — только намерения или закрытые дела.
    return STYLE_GRAY


@router.get("/graph")
def get_graph(db: Session = Depends(get_db)) -> dict:
    """Отдаёт граф (узлы и связи) для React Flow.

    Берём всех ``Person``, у которых есть хотя бы одна договорённость
    (``Agreement``). Цвет узла кодирует квадрант дела:

    - красный    — незакрытый agreement, debtor="me"  (мой долг);
    - синий      — незакрытый agreement, debtor="them" (их долг);
    - фиолетовый — незакрытый request,   debtor="me"  (просят меня);
    - оранжевый  — незакрытый request,   debtor="them" (прошу я);
    - серый      — только intention или закрытые дела.

    Выборка ограничена первыми GRAPH_PERSONS_LIMIT людьми, чтобы браузер
    не завис на тысячах узлов.
    """
    persons = (
        db.query(Person)
        .join(Agreement, Agreement.person_id == Person.id)
        .distinct()
        .order_by(Person.id)
        .limit(GRAPH_PERSONS_LIMIT)
        .all()
    )

    nodes: list[dict] = [ME_NODE]
    edges: list[dict] = []

    for person in persons:
        agreements = list(person.agreements)
        node_id = f"person-{person.id}"
        nodes.append(
            {
                "id": node_id,
                "type": "default",
                "position": {
                    "x": random.randint(-GRAPH_SPREAD, GRAPH_SPREAD),
                    "y": random.randint(-GRAPH_SPREAD, GRAPH_SPREAD),
                },
                "data": {
                    "label": person.first_name,
                    "type": "person",
                    "telegramUsername": person.username,
                    "agreements_count": len(agreements),
                    "agreements": [
                        _serialize_agreement(a) for a in agreements
                    ],
                },
                "style": _pick_node_style(agreements),
            }
        )
        edges.append(
            {
                "id": f"e-me-{node_id}",
                "source": "me",
                "target": node_id,
            }
        )

    return {"nodes": nodes, "edges": edges}


@router.get("/graph/agreements")
def get_graph_agreements(db: Session = Depends(get_db)) -> list[dict]:
    """Отдаёт список всех договорённостей для отрисовки на графе.

    Формат элемента совпадает с ожиданиями фронтенда React Flow:
    person_name (кто), case_name (кейс), text (суть), deadline (дата или null),
    type (commitment/intention/closed) и debtor (me/them).

    Дедлайн приводим к ISO-строке "YYYY-MM-DD"; если его нет — отдаём null,
    чтобы фронтенд единообразно обрабатывал отсутствие срока.
    """
    rows = (
        db.query(Agreement, Person.first_name)
        .join(Person, Person.id == Agreement.person_id)
        .order_by(Agreement.created_at.desc(), Agreement.id.desc())
        .all()
    )

    return [
        {
            "person_name": person_name,
            "case_name": agreement.case_name,
            "text": agreement.text,
            "deadline": (
                agreement.deadline.strftime("%Y-%m-%d")
                if agreement.deadline
                else None
            ),
            "type": agreement.type,
            "debtor": agreement.debtor,
        }
        for agreement, person_name in rows
    ]
