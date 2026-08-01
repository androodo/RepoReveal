"use client";

import type { AnalysisDetail, FileListItem } from "@/types/analysis";

export function OverviewTab({
  analysis,
  onOpenFilePath,
  files,
}: {
  analysis: AnalysisDetail;
  files: FileListItem[];
  onOpenFilePath: (path: string) => void;
}) {
  const stats = analysis.statistics || {};
  const summary = analysis.deterministic_summary;
  const overview = analysis.ai_overview;
  const cards = [
    { label: "Python files", value: stats.python_file_count ?? 0 },
    { label: "Lines of Python", value: stats.lines_of_python ?? 0 },
    { label: "Internal edges", value: stats.internal_dependency_edges ?? 0 },
    { label: "Entry points", value: stats.entry_point_count ?? 0 },
    { label: "Test files", value: stats.test_file_count ?? 0 },
    { label: "Parse warnings", value: stats.parse_warning_count ?? 0 },
  ];

  const pathToId = new Map(files.map((f) => [f.path, f.id]));

  return (
    <div className="space-y-8">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <div
            key={card.label}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
          >
            <div className="text-xs uppercase tracking-wide text-[var(--muted)]">{card.label}</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums">{card.value}</div>
          </div>
        ))}
      </div>

      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <h3 className="text-base font-semibold">Architecture overview</h3>
        {!overview && (
          <p className="mt-3 text-sm text-[var(--muted)]">
            {analysis.ai_available === false
              ? "AI explanations are unavailable. Deterministic analysis results below are still complete."
              : "AI overview was not generated for this analysis. Deterministic findings are shown below."}
          </p>
        )}
        {overview && (
          <div className="mt-4 space-y-4 text-sm leading-6 text-[var(--foreground)]">
            <div>
              <h4 className="font-medium">What this repository appears to do</h4>
              <p className="mt-1 text-[var(--muted)]">{overview.project_purpose}</p>
            </div>
            <div>
              <h4 className="font-medium">How it is organized</h4>
              <p className="mt-1 text-[var(--muted)]">{overview.architecture_summary}</p>
            </div>
            {overview.main_components && overview.main_components.length > 0 && (
              <div>
                <h4 className="font-medium">Main components</h4>
                <ul className="mt-2 space-y-2">
                  {overview.main_components.map((c) => (
                    <li key={c.name} className="rounded-md bg-[var(--surface-2)] px-3 py-2">
                      <div className="font-medium">{c.name}</div>
                      <div className="text-[var(--muted)]">{c.description}</div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {overview.execution_flow && overview.execution_flow.length > 0 && (
              <div>
                <h4 className="font-medium">Main execution or request flow</h4>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-[var(--muted)]">
                  {overview.execution_flow.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </div>
            )}
            {overview.caveats && overview.caveats.length > 0 && (
              <div>
                <h4 className="font-medium">Analysis limitations</h4>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-[var(--muted)]">
                  {overview.caveats.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <h3 className="text-base font-semibold">Start here</h3>
        <ul className="mt-4 space-y-3">
          {(summary?.start_here || []).map((item) => (
            <li key={item.path} className="flex flex-col gap-1 border-b border-[var(--border)] pb-3 last:border-0">
              <button
                type="button"
                className="text-left font-mono text-sm text-[var(--accent)] hover:underline"
                onClick={() => onOpenFilePath(item.path)}
              >
                {item.path}
              </button>
              <div className="text-xs text-[var(--muted)]">
                {item.category}
                {item.is_entry_point ? " · entry point" : ""}
              </div>
              <p className="text-sm text-[var(--muted)]">{item.why}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <h3 className="text-base font-semibold">Key files</h3>
        <ul className="mt-4 space-y-3">
          {(summary?.important_files || []).slice(0, 10).map((item) => (
            <li key={item.path} className="border-b border-[var(--border)] pb-3 last:border-0">
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  className="text-left font-mono text-sm text-[var(--accent)] hover:underline"
                  onClick={() => {
                    if (pathToId.has(item.path)) onOpenFilePath(item.path);
                    else onOpenFilePath(item.path);
                  }}
                >
                  {item.path}
                </button>
                <span className="text-xs tabular-nums text-[var(--muted)]">
                  {Math.round(item.importance_score)}
                </span>
              </div>
              <p className="mt-1 text-sm text-[var(--muted)]">{item.reason}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <h3 className="text-base font-semibold">Detected entry points</h3>
        <ul className="mt-4 space-y-3">
          {(summary?.entry_points || []).map((item) => (
            <li key={item.path}>
              <button
                type="button"
                className="font-mono text-sm text-[var(--accent)] hover:underline"
                onClick={() => onOpenFilePath(item.path)}
              >
                {item.path}
              </button>
              <div className="text-xs text-[var(--muted)]">
                confidence: {item.confidence || "n/a"}
              </div>
              <ul className="mt-1 list-disc pl-5 text-sm text-[var(--muted)]">
                {item.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
