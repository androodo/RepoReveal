"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, explainFile, getFileDetail, getImpact } from "@/lib/api";
import type { AskPayload, ImpactPayload } from "@/types/analysis";

export function FileDetailsPanel({
  analysisId,
  fileId,
  onClose,
  aiAvailable,
}: {
  analysisId: string;
  fileId: string;
  onClose: () => void;
  aiAvailable: boolean;
}) {
  const detailQuery = useQuery({
    queryKey: ["file", analysisId, fileId],
    queryFn: () => getFileDetail(analysisId, fileId),
  });

  const explainMutation = useMutation({
    mutationFn: () => explainFile(analysisId, fileId),
  });
  const impactMutation = useMutation({
    mutationFn: () => getImpact(analysisId, fileId),
  });

  const detail = detailQuery.data;
  const explanation = explainMutation.data as AskPayload | undefined;
  const impact = impactMutation.data as ImpactPayload | undefined;

  return (
    <aside className="flex h-full w-full flex-col border-l border-[var(--border)] bg-[var(--surface)] lg:w-[380px]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <h3 className="text-sm font-semibold">File details</h3>
        <button type="button" onClick={onClose} aria-label="Close details" className="text-[var(--muted)]">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4 text-sm">
        {detailQuery.isLoading && <p className="text-[var(--muted)]">Loading…</p>}
        {detail && (
          <>
            <div>
              <div className="font-mono text-xs break-all">{detail.path}</div>
              <div className="mt-1 text-xs text-[var(--muted)]">
                {detail.module_name || "—"} · {detail.category}
              </div>
            </div>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-[var(--muted)]">Lines</dt>
                <dd>{detail.line_count}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Est. complexity</dt>
                <dd>{detail.estimated_complexity}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Imported by</dt>
                <dd>{detail.incoming_count}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Imports</dt>
                <dd>{detail.outgoing_count}</dd>
              </div>
            </dl>
            {detail.is_entry_point && (
              <div>
                <h4 className="font-medium">Entry-point reasons</h4>
                <ul className="mt-1 list-disc pl-4 text-[var(--muted)]">
                  {(detail.entrypoint_reasons || []).map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <h4 className="font-medium">Functions & classes</h4>
              <ul className="mt-1 space-y-1 font-mono text-xs text-[var(--muted)]">
                {(detail.symbols || []).map((s) => (
                  <li key={`${s.kind}-${s.name}`}>
                    {s.kind}: {s.name} ({s.line_start}-{s.line_end})
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-medium">Internal dependencies</h4>
              <ul className="mt-1 space-y-1 font-mono text-xs text-[var(--muted)]">
                {detail.internal_dependencies.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-medium">Files importing this file</h4>
              <ul className="mt-1 space-y-1 font-mono text-xs text-[var(--muted)]">
                {detail.importers.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-medium">External imports</h4>
              <p className="mt-1 font-mono text-xs text-[var(--muted)]">
                {(detail.external_imports || []).join(", ") || "—"}
              </p>
            </div>
            <a
              href={detail.github_url}
              target="_blank"
              rel="noreferrer"
              className="inline-block text-[var(--accent)] hover:underline"
            >
              View on GitHub
            </a>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={!aiAvailable || explainMutation.isPending}
                onClick={() => explainMutation.mutate()}
              >
                {explainMutation.isPending ? "Explaining…" : "Explain this file"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={impactMutation.isPending}
                onClick={() => impactMutation.mutate()}
              >
                {impactMutation.isPending ? "Computing…" : "Show change impact"}
              </Button>
            </div>
            {!aiAvailable && (
              <p className="text-xs text-[var(--muted)]">
                AI explanations are unavailable without an OpenAI API key.
              </p>
            )}
            {explainMutation.isError && (
              <p className="text-xs text-red-600">
                {explainMutation.error instanceof ApiError
                  ? explainMutation.error.message
                  : "Explanation failed."}
              </p>
            )}
            {explanation && (
              <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
                <h4 className="font-medium">Explanation</h4>
                <p className="mt-2 whitespace-pre-wrap text-[var(--muted)]">{explanation.answer}</p>
                <ul className="mt-3 space-y-1 text-xs">
                  {explanation.citations.map((c) => (
                    <li key={`${c.file_path}-${c.line_start}`} className="font-mono">
                      {c.file_path}:{c.line_start}-{c.line_end} — {c.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {impact && (
              <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
                <h4 className="font-medium">Structural change impact</h4>
                <p className="mt-2 text-xs text-[var(--muted)]">{impact.disclaimer}</p>
                <ImpactList title="Direct dependents" items={impact.direct_dependents} />
                <ImpactList title="Second-level dependents" items={impact.second_level_dependents} />
                <ImpactList title="Related tests" items={impact.related_tests} />
                <ImpactList title="Affected entry points" items={impact.affected_entry_points} />
                <div className="mt-3">
                  <h5 className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                    Representative paths
                  </h5>
                  <ul className="mt-1 space-y-1 font-mono text-xs">
                    {impact.representative_paths.map((path) => (
                      <li key={path.join(">")}>{path.join(" → ")}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

function ImpactList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-3">
      <h5 className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">{title}</h5>
      <ul className="mt-1 space-y-1 font-mono text-xs">
        {items.length === 0 ? <li>—</li> : items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}
