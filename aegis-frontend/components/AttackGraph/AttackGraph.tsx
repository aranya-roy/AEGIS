"use client";

import { useEffect, useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  useReactFlow,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useAegis } from "@/hooks/useAegis";

function Graph() {
  const nodesData = useAegis((s) => s.nodes);
  const { fitView } = useReactFlow();

  const { nodes, edges } = useMemo(() => {
    const depth: Record<string, number> = {};
    const perDepth: Record<number, number> = {};

    const rfNodes: Node[] = nodesData.map((n) => {
      const d = n.parent ? (depth[n.parent] ?? 0) + 1 : 0;
      depth[n.id] = d;
      const idx = perDepth[d] ?? 0;
      perDepth[d] = idx + 1;

      return {
        id: n.id,
        position: { x: idx * 220, y: d * 70 },
        data: { label: n.predicted ? `🔮 ${n.label}` : n.label },
        style: {
          background: n.predicted ? "transparent" : "#1e293b",
          color: "#f1f5f9",
          border: n.predicted ? "2px dashed #f59e0b" : "1px solid #475569",
          borderRadius: 10,
          padding: "8px 14px",
          fontSize: 13,
          width: 190,
        },
      };
    });

    const rfEdges: Edge[] = nodesData
      .filter((n) => n.parent)
      .map((n) => ({
        id: `${n.parent}-${n.id}`,
        source: n.parent as string,
        target: n.id,
        animated: !!n.predicted,
        style: {
          stroke: n.predicted ? "#f59e0b" : "#64748b",
          strokeDasharray: n.predicted ? "6 4" : undefined,
        },
      }));

    return { nodes: rfNodes, edges: rfEdges };
  }, [nodesData]);

  useEffect(() => {
    const t = setTimeout(
      () => fitView({ duration: 400, padding: 0.15, maxZoom: 1 }),
      150
    );
    return () => clearTimeout(t);
  }, [nodes.length, fitView]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      colorMode="dark"
      fitView
      nodesDraggable={false}
      nodesConnectable={false}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={24} color="#1e293b" />
    </ReactFlow>
  );
}

export function AttackGraph() {
  return (
    <div className="h-[520px] rounded-xl border border-slate-800 bg-slate-900/50">
      <ReactFlowProvider>
        <Graph />
      </ReactFlowProvider>
    </div>
  );
} 