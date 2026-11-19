import type { ContactEdge, ContactNode } from '../types/graph';

// Базовый адрес бэкенда. По умолчанию — локальный FastAPI (uvicorn на :8000).
// Можно переопределить через VITE_API_URL при деплое/проксировании.
const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// Ответ эндпоинта GET /api/graph: узлы и связи в формате React Flow.
export interface GraphData {
  nodes: ContactNode[];
  edges: ContactEdge[];
}

/**
 * Загружает граф (узлы и связи) с бэкенда.
 *
 * @throws Error если сервер ответил не-2xx статусом.
 */
export async function fetchGraphData(): Promise<GraphData> {
  const response = await fetch(`${API_BASE_URL}/api/graph`);

  if (!response.ok) {
    throw new Error(`Не удалось загрузить граф: HTTP ${response.status}`);
  }

  return (await response.json()) as GraphData;
}