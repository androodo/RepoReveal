"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, askRepository, getStarterQuestions } from "@/lib/api";
import type { AskPayload } from "@/types/analysis";

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).map((item) => item.trim()).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

export function AskTab({
  analysisId,
  aiAvailable,
}: {
  analysisId: string;
  aiAvailable: boolean;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskPayload | null>(null);
  const starters = useQuery({
    queryKey: ["starters", analysisId],
    queryFn: () => getStarterQuestions(analysisId),
    enabled: true,
  });
  const askMutation = useMutation({
    mutationFn: (q: string) => askRepository(analysisId, q),
    onSuccess: (data) => setAnswer(data),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <h3 className="text-base font-semibold">Ask RepoReveal</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Answers are grounded in retrieved repository evidence with validated citations. This is
          not an unrestricted chatbot.
        </p>
        {!aiAvailable && (
          <p className="mt-3 rounded-md bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--muted)]">
            AI features are unavailable. Configure an OpenAI API key on the backend to enable
            repository Q&A.
          </p>
        )}
        <form
          className="mt-4 flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (!question.trim()) return;
            askMutation.mutate(question.trim());
          }}
        >
          <Input
            placeholder="Ask a question about this repository…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={!aiAvailable}
          />
          <Button type="submit" disabled={!aiAvailable || askMutation.isPending}>
            {askMutation.isPending ? "Thinking…" : "Ask"}
          </Button>
        </form>
        <div className="mt-4 flex flex-wrap gap-2">
          {(starters.data?.questions || []).map((q) => (
            <button
              key={q}
              type="button"
              className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--muted)] hover:bg-[var(--surface-2)]"
              onClick={() => {
                setQuestion(q);
                if (aiAvailable) askMutation.mutate(q);
              }}
            >
              {q}
            </button>
          ))}
        </div>
        {askMutation.isError && (
          <p className="mt-3 text-sm text-red-600">
            {askMutation.error instanceof ApiError
              ? askMutation.error.message
              : "Question failed."}
          </p>
        )}
      </div>

      {answer && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
          <div className="text-xs uppercase tracking-wide text-[var(--muted)]">
            Confidence: {answer.confidence}
          </div>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{answer.answer}</p>
          {answer.citations.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium">Citations</h4>
              <ul className="mt-2 space-y-1 font-mono text-xs text-[var(--muted)]">
                {answer.citations.map((c, index) => (
                  <li key={`${c.file_path}-${c.line_start}-${c.line_end}-${index}`}>
                    {c.file_path}:{c.line_start}-{c.line_end} — {c.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {asStringList(answer.suggested_files).length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium">Suggested files</h4>
              <ul className="mt-2 space-y-1 font-mono text-xs text-[var(--accent)]">
                {asStringList(answer.suggested_files).map((f, index) => (
                  <li key={`${f}-${index}`}>{f}</li>
                ))}
              </ul>
            </div>
          )}
          {asStringList(answer.limitations).length > 0 && (
            <ul className="mt-4 list-disc pl-5 text-xs text-[var(--muted)]">
              {asStringList(answer.limitations).map((l, index) => (
                <li key={`${index}-${l.slice(0, 24)}`}>{l}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
