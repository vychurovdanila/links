import type { Node, Edge } from '@xyflow/react';

// Тип данных для узла (человек или группа)
export interface ContactNodeData extends Record<string, unknown> {
  label: string;
  type: 'person' | 'group';
  telegramUsername?: string;
  status?: 'active' | 'overdue'; // Для красной подсветки дедлайнов
  agreementsCount?: number;
}

// Наш кастомный тип узла
export type ContactNode = Node<ContactNodeData, 'contactNode'>;

// Наш кастомный тип связи (ребра)
export type ContactEdge = Edge;
