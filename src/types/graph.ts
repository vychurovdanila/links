import type { Node, Edge } from '@xyflow/react';

// Договорённость, как её отдаёт бэкенд в data.agreements узла.
export interface Agreement {
  id: number;
  text: string;
  case_name: string | null;
  type: string;
  debtor: string;
  is_approximate: boolean;
  is_completed: boolean;
  deadline: string | null;
}

// Тип данных для узла (человек или группа)
export interface ContactNodeData extends Record<string, unknown> {
  label: string;
  type: 'person' | 'group';
  telegramUsername?: string;
  status?: 'active' | 'overdue'; // Для красной подсветки дедлайнов
  agreementsCount?: number;
  agreements_count?: number;
  agreements?: Agreement[];
}

// Наш кастомный тип узла
export type ContactNode = Node<ContactNodeData, 'contactNode'>;

// Наш кастомный тип связи (ребра)
export type ContactEdge = Edge;
