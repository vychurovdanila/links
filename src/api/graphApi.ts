import type { ContactEdge, ContactNode } from '../types/graph';

// Базовый адрес бэкенда FastAPI (uvicorn на :8000).
// В dev используем LAN-IP ПК, чтобы граф открывался и с телефона в той же
// Wi-Fi сети: localhost с телефона указывал бы на сам телефон, а не на ПК.
// При деплое/проксировании адрес переопределяется через VITE_API_URL.
const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://192.168.0.111:8000';

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

/**
 * Мягко удаляет договорённость (ставит is_archived = true на бэкенде).
 *
 * @throws Error если сервер ответил не-2xx статусом.
 */
export async function archiveAgreement(agreementId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/agreements/${agreementId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Не удалось удалить договорённость: HTTP ${response.status}`);
  }
}

/**
 * Помечает договорённость приоритетной/горящей (priority = 1).
 *
 * @throws Error если сервер ответил не-2xx статусом.
 */
export async function prioritizeAgreement(agreementId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/agreements/${agreementId}/prioritize`, {
    method: 'PUT',
  });

  if (!response.ok) {
    throw new Error(`Не удалось повысить приоритет: HTTP ${response.status}`);
  }
}