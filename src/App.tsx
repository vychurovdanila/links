import { useEffect, useState } from 'react';
import { ReactFlow, Background, Controls, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { fetchGraphData } from './api/graphApi';
import type { Agreement, ContactEdge, ContactNode } from './types/graph';

// Боковая панель с деталями выбранного контакта.
function SidePanel({ node }: { node: ContactNode | null }) {
  return (
    <aside className="flex h-full w-[300px] shrink-0 flex-col overflow-y-auto border-l border-slate-700 bg-slate-950 p-4 text-slate-200">
      {!node ? (
        <p className="text-sm text-slate-400">Выберите контакт</p>
      ) : (
        <>
          <h2 className="mb-1 text-lg font-semibold">{node.data.label}</h2>
          <p className="mb-4 text-xs text-slate-400">
            Договорённостей: {node.data.agreements?.length ?? 0}
          </p>

          <div className="flex flex-col gap-3">
            {(node.data.agreements ?? []).map((agreement: Agreement) => (
              <div
                key={agreement.id}
                className="rounded-md border border-slate-700 bg-slate-900 p-3"
              >
                {agreement.case_name && (
                  <div className="text-[11px] uppercase tracking-wide text-slate-400">
                    {agreement.case_name}
                  </div>
                )}
                <div className="mt-1 text-sm">{agreement.text}</div>
                <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                  <span>{agreement.deadline ?? 'без срока'}</span>
                  <span>{agreement.debtor === 'me' ? 'долг мой' : 'долг на нём'}</span>
                </div>
              </div>
            ))}

            {(node.data.agreements?.length ?? 0) === 0 && (
              <p className="text-sm text-slate-400">Договорённостей нет</p>
            )}
          </div>

          <button
            type="button"
            className="mt-4 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500"
            onClick={() => {
              // Заглушка: переход в чат Telegram появится позже.
              console.log('Открыть чат в Telegram:', node.data.telegramUsername ?? node.data.label);
            }}
          >
            Открыть чат в Telegram
          </button>
        </>
      )}
    </aside>
  );
}

function App() {
  // Инициализируем пустое состояние: данные придут из API.
  const [nodes, setNodes, onNodesChange] = useNodesState<ContactNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<ContactEdge>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<ContactNode | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function loadGraph() {
      try {
        const data = await fetchGraphData();
        if (isCancelled) return;
        setNodes(data.nodes);
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
      <SidePanel node={selectedNode} />
    </div>
  );
}

export default App;
