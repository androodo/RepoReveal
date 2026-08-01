"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

type FileNodeData = {
  fileName: string;
  dir: string;
  category: string;
  isEntryPoint: boolean;
  importance: number;
  fileId: string;
};

function FileNodeComponent({ data, selected }: NodeProps) {
  const d = data as FileNodeData;
  return (
    <div
      className={`min-w-[200px] rounded-md border px-3 py-2 shadow-sm ${
        selected
          ? "border-[var(--accent)] bg-[var(--accent-soft)]"
          : "border-[var(--border)] bg-[var(--surface)]"
      }`}
    >
      <Handle type="target" position={Position.Left} className="!bg-[var(--accent)]" />
      <div className="flex items-center justify-between gap-2">
        <div className="font-mono text-xs font-semibold text-[var(--foreground)]">{d.fileName}</div>
        {d.isEntryPoint && (
          <span className="rounded bg-[var(--accent)] px-1.5 py-0.5 text-[10px] text-[var(--accent-fg)]">
            entry
          </span>
        )}
      </div>
      <div className="mt-0.5 truncate font-mono text-[10px] text-[var(--muted)]">{d.dir}</div>
      <div className="mt-1 flex items-center justify-between text-[10px] text-[var(--muted)]">
        <span>{d.category}</span>
        <span className="tabular-nums">★ {Math.round(d.importance)}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-[var(--accent)]" />
    </div>
  );
}

export const FileNode = memo(FileNodeComponent);
