"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { AnalysisProgress } from "@/components/analysis/analysis-progress";
import { AskTab } from "@/components/analysis/ask-tab";
import { OverviewTab } from "@/components/analysis/overview-tab";
import { FileDetailsPanel } from "@/components/files/file-details-panel";
import { FilesTab } from "@/components/files/files-tab";
import { ArchitectureGraph } from "@/components/graph/architecture-graph";
import { Button } from "@/components/ui/button";
import { getAnalysis, getFiles, reanalyze } from "@/lib/api";
import { formatDate, shortSha } from "@/lib/utils";

type Tab = "overview" | "architecture" | "files" | "ask";

export function AnalysisWorkspace({ analysisId }: { analysisId: string }) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);

  const analysisQuery = useQuery({
    queryKey: ["analysis", analysisId],
    queryFn: () => getAnalysis(analysisId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 1500 : false;
    },
  });

  const completed = analysisQuery.data?.status === "completed";
  const filesQuery = useQuery({
    queryKey: ["files", analysisId],
    queryFn: () => getFiles(analysisId, { page: 1, page_size: 500, sort: "importance" }),
    enabled: completed,
  });

  const retryMutation = useMutation({
    mutationFn: () => reanalyze(analysisId),
    onSuccess: (result) => {
      router.push(`/analyses/${result.analysis_id}`);
    },
  });

  const analysis = analysisQuery.data;
  const files = useMemo(() => filesQuery.data?.items ?? [], [filesQuery.data?.items]);
  const pathToId = useMemo(() => new Map(files.map((f) => [f.path, f.id])), [files]);

  if (analysisQuery.isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="h-8 w-64 animate-pulse rounded bg-[var(--surface-2)]" />
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10">
        <p className="text-[var(--muted)]">Analysis not found.</p>
      </div>
    );
  }

  const repo = analysis.repository;

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6">
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {repo ? `${repo.owner}/${repo.name}` : "Repository"}
            </h1>
            <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
              {repo?.description || "No description provided."}
            </p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
              <span>branch {repo?.default_branch || "—"}</span>
              <span className="font-mono">{shortSha(analysis.commit_sha)}</span>
              <span>{analysis.statistics?.python_file_count ?? "—"} Python files</span>
              <span>{formatDate(analysis.completed_at || analysis.created_at)}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {repo && (
              <a
                href={repo.github_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--surface-2)]"
              >
                GitHub <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
            <Button
              type="button"
              variant="secondary"
              onClick={() => retryMutation.mutate()}
              disabled={retryMutation.isPending}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Reanalyze
            </Button>
          </div>
        </div>
      </div>

      {(analysis.status === "queued" || analysis.status === "processing") && (
        <div className="mt-6">
          <AnalysisProgress stage={analysis.stage} progress={analysis.progress} />
        </div>
      )}

      {analysis.status === "failed" && (
        <div className="mt-6">
          <AnalysisProgress
            stage={analysis.stage}
            progress={analysis.progress}
            errorMessage={analysis.error_message}
            onRetry={() => retryMutation.mutate()}
          />
        </div>
      )}

      {completed && (
        <div className="mt-6 flex flex-col gap-4 lg:flex-row">
          <div className="min-w-0 flex-1">
            <div className="mb-4 flex flex-wrap gap-1 border-b border-[var(--border)]">
              {(
                [
                  ["overview", "Overview"],
                  ["architecture", "Architecture"],
                  ["files", "Files"],
                  ["ask", "Ask RepoReveal"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className={`border-b-2 px-3 py-2 text-sm ${
                    tab === id
                      ? "border-[var(--accent)] text-[var(--foreground)]"
                      : "border-transparent text-[var(--muted)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === "overview" && (
              <OverviewTab
                analysis={analysis}
                files={files}
                onOpenFilePath={(path) => {
                  const id = pathToId.get(path);
                  if (id) {
                    setSelectedFileId(id);
                    setTab("files");
                  }
                }}
              />
            )}
            {tab === "architecture" && (
              <ArchitectureGraph
                analysisId={analysisId}
                onSelectFileId={(id) => setSelectedFileId(id)}
              />
            )}
            {tab === "files" && (
              <FilesTab files={files} onSelectFile={(id) => setSelectedFileId(id)} />
            )}
            {tab === "ask" && (
              <AskTab analysisId={analysisId} aiAvailable={Boolean(analysis.ai_available)} />
            )}
          </div>

          {selectedFileId && (
            <FileDetailsPanel
              analysisId={analysisId}
              fileId={selectedFileId}
              onClose={() => setSelectedFileId(null)}
              aiAvailable={Boolean(process.env.NEXT_PUBLIC_API_BASE_URL) ? analysis.ai_available : analysis.ai_available}
            />
          )}
        </div>
      )}
    </div>
  );
}
