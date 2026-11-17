import type { ContactNode, ContactEdge } from '../types/graph';

// Тестовые узлы (Центр - ты, вокруг - группы и люди)
export const initialNodes: ContactNode[] = [
  {
    id: 'me',
    type: 'default',
    position: { x: 400, y: 300 },
    data: { label: 'Данила (Я)', type: 'person' },
    style: { background: '#1e293b', color: 'white', border: '2px solid #3b82f6', borderRadius: '50%', padding: '20px' },
  },
  {
    id: 'group-work',
    type: 'default',
    position: { x: 200, y: 100 },
    data: { label: 'Работа', type: 'group' },
    style: { background: '#334155', color: 'white', borderRadius: '10px' },
  },
  {
    id: 'group-family',
    type: 'default',
    position: { x: 600, y: 500 },
    data: { label: 'Семья', type: 'group' },
    style: { background: '#334155', color: 'white', borderRadius: '10px' },
  },
  {
    id: 'person-petya',
    type: 'default',
    position: { x: 150, y: 200 },
    data: { label: 'Петя', type: 'person', telegramUsername: '@petya', status: 'overdue', agreementsCount: 2 },
    style: { background: '#7f1d1d', color: 'white', border: '2px solid #ef4444', borderRadius: '50%' }, // Красный из-за долга
  },
  {
    id: 'person-vasya',
    type: 'default',
    position: { x: 300, y: 50 },
    data: { label: 'Вася', type: 'person', telegramUsername: '@vasya', status: 'active' },
    style: { background: '#1e293b', color: 'white', borderRadius: '50%' },
  }
];

// Тестовые связи
export const initialEdges: ContactEdge[] = [
  { id: 'e-me-petya', source: 'me', target: 'person-petya', label: 'Долг: Отчет', animated: true, style: { stroke: '#ef4444' } },
  { id: 'e-me-vasya', source: 'me', target: 'person-vasya', label: 'Договоренность', style: { stroke: '#3b82f6' } },
  { id: 'e-me-work', source: 'me', target: 'group-work', style: { stroke: '#64748b', strokeDasharray: '5 5' } },
  { id: 'e-me-family', source: 'me', target: 'group-family', style: { stroke: '#64748b', strokeDasharray: '5 5' } },
];
