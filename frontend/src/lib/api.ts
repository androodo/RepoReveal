import type {
  AnalysisDetail,
  AskPayload,
  FileDetail,
  FileListItem,
  GraphPayload,
  ImpactPayload,
} from "@/types/analysis";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let body: { error?: { code?: string; message?: string; details?: unknown } } | null =
      null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw new ApiError(
      response.status,
      body?.error?.code || "REQUEST_FAILED",
      body?.error?.message || `Request failed (${response.status})`,
      body?.error?.details ?? null,
    );
  }
  return response.json() as Promise<T>;
}

export function createAnalysis(repositoryUrl: string, force = false) {
  return request<{ analysis_id: string; status: string; cached: boolean }>("/analyses", {
    method: "POST",
    body: JSON.stringify({ repository_url: repositoryUrl, force }),
  });
}

export function getAnalysis(analysisId: string) {
  return request<AnalysisDetail>(`/analyses/${analysisId}`);
}

export function getGraph(
  analysisId: string,
  params: Record<string, string | number | boolean | undefined>,
) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") qs.set(key, String(value));
  });
  return request<GraphPayload>(`/analyses/${analysisId}/graph?${qs.toString()}`);
}

export function getFiles(
  analysisId: string,
  params: Record<string, string | number | boolean | undefined>,
) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") qs.set(key, String(value));
  });
  return request<{ items: FileListItem[]; total: number; page: number; page_size: number }>(
    `/analyses/${analysisId}/files?${qs.toString()}`,
  );
}

export function getFileDetail(analysisId: string, fileId: string) {
  return request<FileDetail>(`/analyses/${analysisId}/files/${fileId}`);
}

export function explainFile(analysisId: string, fileId: string) {
  return request<AskPayload>(`/analyses/${analysisId}/files/${fileId}/explain`, {
    method: "POST",
  });
}

export function getImpact(analysisId: string, fileId: string) {
  return request<ImpactPayload>(`/analyses/${analysisId}/files/${fileId}/impact`);
}

export function askRepository(analysisId: string, question: string) {
  return request<AskPayload>(`/analyses/${analysisId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function getStarterQuestions(analysisId: string) {
  return request<{ questions: string[] }>(`/analyses/${analysisId}/starter-questions`);
}

export function reanalyze(analysisId: string) {
  return request<{ analysis_id: string; status: string; cached: boolean }>(
    `/analyses/${analysisId}/reanalyze`,
    { method: "POST" },
  );
}
