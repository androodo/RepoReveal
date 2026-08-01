const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  fetching_repository: "Fetching repository",
  downloading_source: "Downloading source",
  scanning_files: "Scanning files",
  parsing_python: "Parsing Python",
  building_graph: "Building dependency graph",
  creating_index: "Creating code index",
  generating_overview: "Generating AI overview",
  complete: "Complete",
};

const ORDER = [
  "fetching_repository",
  "downloading_source",
  "scanning_files",
  "parsing_python",
  "building_graph",
  "creating_index",
  "generating_overview",
  "complete",
];

export function AnalysisProgress({
  stage,
  progress,
  errorMessage,
  onRetry,
}: {
  stage: string;
  progress: number;
  errorMessage?: string | null;
  onRetry?: () => void;
}) {
  if (errorMessage) {
    return (
      <div className="rounded-lg border border-red-300 bg-red-50 p-6 dark:border-red-900 dark:bg-red-950/40">
        <h2 className="text-lg font-semibold text-red-700 dark:text-red-300">Analysis failed</h2>
        <p className="mt-2 text-sm text-red-700/90 dark:text-red-200">{errorMessage}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 rounded-md bg-[var(--accent)] px-3 py-2 text-sm text-[var(--accent-fg)]"
          >
            Retry analysis
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Analyzing repository</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {STAGE_LABELS[stage] || stage} · {progress}%
          </p>
        </div>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div
          className="h-full rounded-full bg-[var(--accent)] transition-all"
          style={{ width: `${Math.max(progress, 4)}%` }}
        />
      </div>
      <ol className="mt-6 grid gap-2 sm:grid-cols-2">
        {ORDER.map((key) => {
          const idx = ORDER.indexOf(key);
          const currentIdx = ORDER.indexOf(stage);
          const done = currentIdx > idx || stage === "complete";
          const active = stage === key;
          return (
            <li
              key={key}
              className={`rounded-md border px-3 py-2 text-sm ${
                active
                  ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--foreground)]"
                  : done
                    ? "border-[var(--border)] text-[var(--foreground)]"
                    : "border-transparent text-[var(--muted)]"
              }`}
            >
              {STAGE_LABELS[key]}
            </li>
          );
        })}
      </ol>
      <p className="mt-6 text-sm text-[var(--muted)]">
        RepoReveal analyzes source text only. It never executes repository code.
      </p>
    </div>
  );
}
