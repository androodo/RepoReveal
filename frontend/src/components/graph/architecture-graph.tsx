"use client";

import dagre from "@dagrejs/dagre";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  useEdgesState,
  useNodesState,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getGraph } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FileNode } from "@/components/graph/file-node";

const nodeTypes = { file: FileNode };

function layoutGraph(nodes: Node[], edges: Edge[]) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 80 });
  nodes.forEach((node) => g.setNode(node.id, { width: 220, height: 72 }));
  edges.forEach((edge) => g.setEdge(edge.source, edge.target));
  dagre.layout(g);
  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - 110, y: pos.y - 36 },
    };
  });
}

function GraphInner({
  analysisId,
  onSelectFileId,
}: {
  analysisId: string;
  onSelectFileId: (fileId: string) => void;
}) {
  const [limit, setLimit] = useState(50);
  const [includeTests, setIncludeTests] = useState(false);
  const [entryOnly, setEntryOnly] = useState(false);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const { fitView } = useReactFlow();

  const graphQuery = useQuery({
    queryKey: ["graph", analysisId, limit, includeTests, entryOnly, category, search],
    queryFn: () =>
      getGraph(analysisId, {
        limit,
        include_tests: includeTests,
        entry_points_only: entryOnly,
        category: category || undefined,
        search: search || undefined,
      }),
  });

  const built = useMemo(() => {
    const payload = graphQuery.data;
    if (!payload) return { nodes: [] as Node[], edges: [] as Edge[] };
    const nodes: Node[] = payload.nodes.map((n) => {
      const path = String(n.path || n.id);
      const parts = path.split("/");
      const fileName = parts[parts.length - 1] || path;
      const dir = parts.slice(0, -1).join("/") || ".";
      return {
        id: path,
        type: "file",
        position: { x: 0, y: 0 },
        data: {
          fileName,
          dir,
          category: String(n.category || "Other"),
          isEntryPoint: Boolean(n.is_entry_point),
          importance: Number(n.importance_score || 0),
          fileId: String(n.file_id || n.id || ""),
        },
      };
    });
    const edges: Edge[] = payload.edges.map((e, idx) => ({
      id: `${e.source}-${e.target}-${idx}`,
      source: e.source,
      target: e.target,
      animated: false,
    }));
    return { nodes: layoutGraph(nodes, edges), edges };
  }, [graphQuery.data]);

  const [nodes, setNodes, onNodesChange] = useNodesState(built.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(built.edges);

  useEffect(() => {
    setNodes(built.nodes);
    setEdges(built.edges);
    const t = setTimeout(() => fitView({ padding: 0.2 }), 50);
    return () => clearTimeout(t);
  }, [built, setNodes, setEdges, fitView]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="max-w-xs"
          placeholder="Search nodes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All categories</option>
          {[
            "Entry Point",
            "API / Routes",
            "Services",
            "Models / Data",
            "Core / Domain",
            "Configuration",
            "CLI",
            "Scripts",
            "Tests",
            "Utilities",
            "Migrations",
            "Other",
          ].map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <label className="inline-flex items-center gap-1.5 text-sm text-[var(--muted)]">
          <input
            type="checkbox"
            checked={includeTests}
            onChange={(e) => setIncludeTests(e.target.checked)}
          />
          Tests
        </label>
        <label className="inline-flex items-center gap-1.5 text-sm text-[var(--muted)]">
          <input type="checkbox" checked={entryOnly} onChange={(e) => setEntryOnly(e.target.checked)} />
          Entry points only
        </label>
        <label className="inline-flex items-center gap-1.5 text-sm text-[var(--muted)]">
          Limit
          <input
            type="number"
            min={10}
            max={200}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value) || 50)}
            className="w-20 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1"
          />
        </label>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            setNodes(layoutGraph(nodes, edges));
            setTimeout(() => fitView({ padding: 0.2 }), 30);
          }}
        >
          Reset layout
        </Button>
      </div>
      <div className="h-[560px] overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          onNodeClick={(_, node) => {
            const fileId = String(node.data.fileId || "");
            if (fileId) onSelectFileId(fileId);
          }}
          minZoom={0.2}
          maxZoom={1.5}
        >
          <Background gap={18} size={1} />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </div>
      {graphQuery.data?.truncated && (
        <p className="text-xs text-[var(--muted)]">
          Graph truncated to the current node limit. Increase the limit to see more files.
        </p>
      )}
    </div>
  );
}

export function ArchitectureGraph({
  analysisId,
  onSelectFileId,
}: {
  analysisId: string;
  onSelectFileId: (fileId: string) => void;
}) {
  return (
    <ReactFlowProvider>
      <GraphInner analysisId={analysisId} onSelectFileId={onSelectFileId} />
    </ReactFlowProvider>
  );
}
