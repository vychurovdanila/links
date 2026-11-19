import { useEffect, useState } from 'react';
import { ReactFlow, Background, Controls, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { fetchGraphData } from './api/graphApi';
import type { ContactEdge, ContactNode } from './types/graph';

function App() {
  // Инициализируем пустое состояние: данные придут из API.
  const [nodes, setNodes, onNodesChange] = useNodesState<ContactNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<ContactEdge>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    <div className="h-screen w-screen bg-slate-900">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        preventScrolling={true}
        zoomOnPinch={true}
        panOnDrag={true}
        fitView
      >
        <Background color="#334155" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
}

export default App;
