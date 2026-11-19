"""HTTP-эндпоинты домена links.

Здесь собраны роутеры, которые подключаются к приложению в main.py.
Данные для графа отдаются в формате, совместимом с React Flow:
{"nodes": [...], "edges": [...]}.
"""

import random

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Person

router = APIRouter(prefix="/api", tags=["graph"])

# Максимум людей в одном ответе графа (защита браузера от тысяч узлов).
# Пагинация появится позже — пока отдаём первые N контактов с Telegram.
GRAPH_PERSONS_LIMIT = 50

# Радиус разброса случайных позиций узлов вокруг центра (в пикселях React Flow).
GRAPH_SPREAD = 400

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


@router.get("/graph")
def get_graph(db: Session = Depends(get_db)) -> dict:
    """Отдаёт граф (узлы и связи) для React Flow.

    Берём только ``Person`` с заполненным ``telegram_id`` — это контакты,
    с которыми есть чаты. Выборка ограничена первыми GRAPH_PERSONS_LIMIT
    людьми, чтобы браузер не завис на тысячах узлов.
    """
    persons = (
        db.query(Person)
        .filter(Person.telegram_id.isnot(None))
        .order_by(Person.id)
        .limit(GRAPH_PERSONS_LIMIT)
        .all()
    )

    nodes: list[dict] = [ME_NODE]
    edges: list[dict] = []

    for person in persons:
        node_id = f"person-{person.id}"
        nodes.append(
            {
                "id": node_id,
                "type": "default",
                "position": {
                    "x": random.randint(-GRAPH_SPREAD, GRAPH_SPREAD),
                    "y": random.randint(-GRAPH_SPREAD, GRAPH_SPREAD),
                },
                "data": {"label": person.first_name},
                "style": {
                    "background": "#1e293b",
                    "color": "white",
                    "border": "2px solid #3b82f6",
                    "borderRadius": "50%",
                    "padding": "10px",
                },
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
