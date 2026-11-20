import { useEffect, useState } from 'react';
import { ReactFlow, Background, Controls, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { archiveAgreement, fetchGraphData, prioritizeAgreement } from './api/graphApi';
import type { Agreement, ContactEdge, ContactNode } from './types/graph';

// Ключ localStorage со списком id скрытых (мягко удалённых) договорённостей.
// Нужен, чтобы карточка не возвращалась после обновления страницы.
const HIDDEN_AGREEMENTS_KEY = 'links.hiddenAgreements';

// Человекочитаемый тип записи и сторона, на которой «мяч».
const TYPE_LABELS: Record<string, string> = {
  agreement: 'Договорённость',
  request: 'Просьба',
  intention: 'Намерение',
};

function getTypeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type;
}

function getDebtorLabel(type: string, debtor: string): string {
  // Для просьбы и договорённости «должник» — это тот, кто должен выполнить.
  const isMe = debtor === 'me';
  if (type === 'request') {
    return isMe ? 'Просьба: Я' : 'Просьба: Они';
  }
  if (type === 'agreement') {
    return isMe ? 'Долг: Я' : 'Долг: Они';
  }
  return isMe ? 'Намерение: Я' : 'Намерение: Они';
}

// Цвет карточки по типу записи и должнику:
//   красный    — agreement, debtor="me"  (мой долг);
//   синий      — agreement, debtor="them" (их долг);
//   фиолетовый — request,   debtor="me"  (просят меня);
//   оранжевый  — request,   debtor="them" (прошу я);
//   серый      — intention и прочее.
function getCardClassName(agreement: Agreement): string {
  const base = 'rounded-md border-l-4 p-3 text-slate-100';
  if (agreement.type === 'agreement') {
    return agreement.debtor === 'me'
      ? `${base} border-red-500 bg-red-900/20`
      : `${base} border-blue-500 bg-blue-900/20`;
  }
  if (agreement.type === 'request') {
    return agreement.debtor === 'me'
      ? `${base} border-purple-500 bg-purple-900/20`
      : `${base} border-orange-500 bg-orange-900/20`;
  }
  return `${base} border-slate-500 bg-slate-800`;
}

// Боковая панель с деталями выбранного контакта.
// onArchive/onPrioritize — обработчики действий над договорённостью.
function SidePanel({
  node,
  onArchive,
  onPrioritize,
}: {
  node: ContactNode | null;
  onArchive: (agreement: Agreement) => void;
  onPrioritize: (agreement: Agreement) => void;
}) {
  // Открывает чат Telegram и копирует текст договорённости в буфер обмена.
  const openInTelegram = async (agreement: Agreement) => {
    const username = node?.data.telegramUsername;
    try {
      await navigator.clipboard.writeText(agreement.text);
    } catch {
      // Буфер обмена может быть недоступен (нет разрешения / не https).
      window.alert('Не удалось скопировать текст в буфер обмена');
      return;
    }
    if (!username) {
      window.alert('У контакта нет username в Telegram');
      return;
    }
    window.open(`tg://resolve?domain=${encodeURIComponent(username)}`, '_blank');
  };

  const agreements = node?.data.agreements ?? [];

  return (
    <aside className="flex h-full w-[300px] shrink-0 flex-col overflow-y-auto border-l border-slate-700 bg-slate-950 p-4 text-slate-200">
      {!node ? (
        <p className="text-sm text-slate-400">Выберите контакт</p>
      ) : (
        <>
          <h2 className="mb-1 text-lg font-semibold">{node.data.label}</h2>
          <p className="mb-4 text-xs text-slate-400">Договорённостей: {agreements.length}</p>

          <div className="flex flex-col gap-3">
            {agreements.map((agreement: Agreement) => (
              <div key={agreement.id} className={getCardClassName(agreement)}>
                {agreement.case_name && (
                  <div className="text-[11px] uppercase tracking-wide text-slate-300">
                    {agreement.case_name}
                  </div>
                )}
                <div className="mt-1 text-sm">{agreement.text}</div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                  <span className="rounded bg-slate-800 px-1.5 py-0.5">
                    [{getTypeLabel(agreement.type)}]
                  </span>
                  <span className="rounded bg-slate-800 px-1.5 py-0.5">
                    [{getDebtorLabel(agreement.type, agreement.debtor)}]
                  </span>
                  <span className="ml-auto">{agreement.deadline ?? 'без срока'}</span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    title="Удалить"
                    aria-label="Удалить"
                    className="rounded bg-slate-800 px-2 py-1 text-xs hover:bg-slate-700"
                    onClick={() => onArchive(agreement)}
                  >
                    🗑️
                  </button>
                  <button
                    type="button"
                    title="Приоритет"
                    aria-label="Приоритет"
                    className="rounded bg-slate-800 px-2 py-1 text-xs hover:bg-slate-700"
                    onClick={() => onPrioritize(agreement)}
                  >
                    🔥
                  </button>
                  <button
                    type="button"
                    className="ml-auto rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-500"
                    onClick={() => void openInTelegram(agreement)}
                  >
                    Открыть в TG
                  </button>
                </div>
              </div>
            ))}

            {agreements.length === 0 && (
              <p className="text-sm text-slate-400">Договорённостей нет</p>
            )}
          </div>
        </>
      )}
    </aside>
  );
}

// Читает id скрытых договорённостей из localStorage (устойчиво к битым данным).
function loadHiddenAgreementIds(): Set<number> {
  try {
    const raw = window.localStorage.getItem(HIDDEN_AGREEMENTS_KEY);
    if (!raw) return new Set();
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((id): id is number => typeof id === 'number'));
  } catch {
    return new Set();
  }
}

// Убирает скрытые договорённости из данных узла.
function filterAgreements(node: ContactNode, hidden: Set<number>): ContactNode {
  const agreements = node.data.agreements ?? [];
  return {
    ...node,
    data: {
      ...node.data,
      agreements: agreements.filter((a) => !hidden.has(a.id)),
    },
  };
}

function App() {
  // Инициализируем пустое состояние: данные придут из API.
  const [nodes, setNodes, onNodesChange] = useNodesState<ContactNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<ContactEdge>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<ContactNode | null>(null);
  // Id договорённостей, скрытых локально (мягко удалённых).
  const [hiddenIds, setHiddenIds] = useState<Set<number>>(() => loadHiddenAgreementIds());

  // Сохраняет список скрытых id в localStorage и обновляет состояние.
  const hideAgreement = (id: number) => {
    setHiddenIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      try {
        window.localStorage.setItem(HIDDEN_AGREEMENTS_KEY, JSON.stringify([...next]));
      } catch {
        // localStorage может быть недоступен (приватный режим) — игнорируем.
      }
      return next;
    });
    setNodes((prev) => prev.map((n) => filterAgreements(n, new Set([id]))));
    setSelectedNode((prev) => (prev ? filterAgreements(prev, new Set([id])) : prev));
  };

  // Помечает договорённость приоритетной: локально обновляет type/debtor/priority.
  const markPrioritized = (agreement: Agreement) => {
    const patch = (a: Agreement): Agreement =>
      a.id === agreement.id
        ? {
            ...a,
            priority: 1,
            type: a.type === 'request' ? 'agreement' : a.type,
          }
        : a;
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        data: { ...n.data, agreements: (n.data.agreements ?? []).map(patch) },
      })),
    );
    setSelectedNode((prev) =>
      prev ? { ...prev, data: { ...prev.data, agreements: (prev.data.agreements ?? []).map(patch) } } : prev,
    );
  };

  const handleArchive = async (agreement: Agreement) => {
    try {
      await archiveAgreement(agreement.id);
      hideAgreement(agreement.id);
    } catch (e) {
      window.alert(e instanceof Error ? e.message : 'Не удалось удалить договорённость');
    }
  };

  const handlePrioritize = async (agreement: Agreement) => {
    try {
      await prioritizeAgreement(agreement.id);
      markPrioritized(agreement);
    } catch (e) {
      window.alert(e instanceof Error ? e.message : 'Не удалось повысить приоритет');
    }
  };

  useEffect(() => {
    let isCancelled = false;

    async function loadGraph() {
      try {
        const data = await fetchGraphData();
        if (isCancelled) return;
        // Скрываем локально удалённые договорённости, чтобы они не вернулись.
        setNodes(
          data.nodes.map((node) =>
            node.data.type === 'person' ? filterAgreements(node as ContactNode, hiddenIds) : node,
          ),
        );
        setEdges(data.edges);
      } catch (e) {
        if (isCancelled) return;
        setError(e instanceof Error ? e.message : 'Неизвестная ошибка загрузки графа');
      } finally {
        if (!isCancelled) setIsLoading(false);
      }
    }

    loadGraph();

    return () => {
      isCancelled = true;
    };
  }, [setNodes, setEdges]);

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-900 text-lg text-slate-200">
        Загрузка графа...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-900 p-6 text-center text-lg text-red-400">
        {error}
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen bg-slate-900">
      <div className="h-full flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={(_, node) => setSelectedNode(node as ContactNode)}
          preventScrolling={true}
          zoomOnPinch={true}
          panOnDrag={true}
          fitView
        >
          <Background color="#334155" gap={16} />
          <Controls />
        </ReactFlow>
      </div>
      <SidePanel
        node={selectedNode}
        onArchive={handleArchive}
        onPrioritize={handlePrioritize}
      />
    </div>
  );
}

export default App;
