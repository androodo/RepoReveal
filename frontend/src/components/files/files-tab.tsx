"use client";

import { useMemo, useState } from "react";
import type { FileListItem } from "@/types/analysis";
import { Input } from "@/components/ui/input";

const CATEGORIES = [
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
];

export function FilesTab({
  files,
  onSelectFile,
}: {
  files: FileListItem[];
  onSelectFile: (fileId: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [entryOnly, setEntryOnly] = useState(false);
  const [testsOnly, setTestsOnly] = useState(false);
  const [warningsOnly, setWarningsOnly] = useState(false);
  const [sort, setSort] = useState<"importance" | "incoming" | "outgoing" | "lines" | "complexity">(
    "importance",
  );

  const filtered = useMemo(() => {
    const rows = files.filter((f) => {
      if (search && !f.path.toLowerCase().includes(search.toLowerCase())) return false;
      if (category && f.category !== category) return false;
      if (entryOnly && !f.is_entry_point) return false;
      if (testsOnly && !f.is_test) return false;
      if (warningsOnly && f.parse_status === "ok") return false;
      return true;
    });
    rows.sort((a, b) => {
      const map = {
        importance: a.importance_score - b.importance_score,
        incoming: a.incoming_count - b.incoming_count,
        outgoing: a.outgoing_count - b.outgoing_count,
        lines: a.line_count - b.line_count,
        complexity: a.estimated_complexity - b.estimated_complexity,
      } as const;
      return map[sort] * -1;
    });
    return rows;
  }, [files, search, category, entryOnly, testsOnly, warningsOnly, sort]);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Input
          placeholder="Search by path…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          value={sort}
          onChange={(e) => setSort(e.target.value as typeof sort)}
        >
          <option value="importance">Sort: Importance</option>
          <option value="incoming">Sort: Imported by</option>
          <option value="outgoing">Sort: Imports</option>
          <option value="lines">Sort: Lines</option>
          <option value="complexity">Sort: Complexity</option>
        </select>
        <div className="flex flex-wrap items-center gap-3 text-sm text-[var(--muted)]">
          <label className="inline-flex items-center gap-1.5">
            <input type="checkbox" checked={entryOnly} onChange={(e) => setEntryOnly(e.target.checked)} />
            Entry points
          </label>
          <label className="inline-flex items-center gap-1.5">
            <input type="checkbox" checked={testsOnly} onChange={(e) => setTestsOnly(e.target.checked)} />
            Tests
          </label>
          <label className="inline-flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={warningsOnly}
              onChange={(e) => setWarningsOnly(e.target.checked)}
            />
            Parse warnings
          </label>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)]">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-[var(--border)] bg-[var(--surface-2)] text-xs uppercase tracking-wide text-[var(--muted)]">
            <tr>
              <th className="px-3 py-2 font-medium">Path</th>
              <th className="px-3 py-2 font-medium">Category</th>
              <th className="px-3 py-2 font-medium">Lines</th>
              <th className="px-3 py-2 font-medium">Complexity</th>
              <th className="px-3 py-2 font-medium">Imported by</th>
              <th className="px-3 py-2 font-medium">Imports</th>
              <th className="px-3 py-2 font-medium">Importance</th>
              <th className="px-3 py-2 font-medium">Flags</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((file) => (
              <tr
                key={file.id}
                className="cursor-pointer border-b border-[var(--border)] hover:bg-[var(--surface-2)]"
                onClick={() => onSelectFile(file.id)}
              >
                <td className="px-3 py-2 font-mono text-xs">{file.path}</td>
                <td className="px-3 py-2">{file.category}</td>
                <td className="px-3 py-2 tabular-nums">{file.line_count}</td>
                <td className="px-3 py-2 tabular-nums">{file.estimated_complexity}</td>
                <td className="px-3 py-2 tabular-nums">{file.incoming_count}</td>
                <td className="px-3 py-2 tabular-nums">{file.outgoing_count}</td>
                <td className="px-3 py-2 tabular-nums">{Math.round(file.importance_score)}</td>
                <td className="px-3 py-2 text-xs text-[var(--muted)]">{file.flags.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="p-6 text-sm text-[var(--muted)]">No files match the current filters.</p>
        )}
      </div>
    </div>
  );
}
