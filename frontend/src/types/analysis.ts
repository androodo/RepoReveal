export type AnalysisStatus =
  | "queued"
  | "processing"
  | "completed"
  | "failed";

export interface RepositorySummary {
  id: string;
  owner: string;
  name: string;
  full_name: string;
  github_url: string;
  description: string | null;
  default_branch: string;
  primary_language: string | null;
  stars: number;
  is_archived: boolean;
}

export interface AnalysisDetail {
  id: string;
  status: AnalysisStatus;
  stage: string;
  progress: number;
  commit_sha: string | null;
  analyzer_version: string;
  repository: RepositorySummary | null;
  statistics: Record<string, number> | null;
  deterministic_summary: {
    entry_points?: Array<{
      path: string;
      confidence: string | null;
      reasons: string[];
      category: string;
    }>;
    important_files?: Array<{
      path: string;
      category: string;
      importance_score: number;
      reason: string;
      is_entry_point: boolean;
    }>;
    start_here?: Array<{
      path: string;
      category: string;
      why: string;
      is_entry_point: boolean;
      importance_score: number;
    }>;
    category_counts?: Record<string, number>;
  } | null;
  ai_overview: {
    project_purpose?: string;
    architecture_summary?: string;
    main_components?: Array<{ name: string; description: string; files: string[] }>;
    execution_flow?: string[];
    start_here?: Array<{ file_path: string; reason: string }>;
    caveats?: string[];
  } | null;
  ai_available: boolean;
  warnings: string[] | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface FileListItem {
  id: string;
  path: string;
  module_name: string | null;
  category: string;
  line_count: number;
  estimated_complexity: number;
  importance_score: number;
  incoming_count: number;
  outgoing_count: number;
  is_test: boolean;
  is_entry_point: boolean;
  parse_status: string;
  flags: string[];
}

export interface FileDetail {
  id: string;
  path: string;
  module_name: string | null;
  category: string;
  category_reasons: string[] | null;
  line_count: number;
  estimated_complexity: number;
  importance_score: number;
  incoming_count: number;
  outgoing_count: number;
  is_test: boolean;
  is_entry_point: boolean;
  entrypoint_confidence: string | null;
  entrypoint_reasons: string[] | null;
  parse_status: string;
  parse_warning: string | null;
  docstring: string | null;
  symbols: Array<{
    name: string;
    kind: string;
    line_start: number;
    line_end: number;
    decorators: string[];
  }> | null;
  external_imports: string[] | null;
  internal_dependencies: string[];
  importers: string[];
  github_url: string;
}

export interface GraphPayload {
  nodes: Array<Record<string, unknown>>;
  edges: Array<{ source: string; target: string; imported_module?: string }>;
  truncated: boolean;
}

export interface ImpactPayload {
  selected_path: string;
  direct_dependents: string[];
  second_level_dependents: string[];
  related_tests: string[];
  affected_entry_points: string[];
  representative_paths: string[][];
  disclaimer: string;
}

export interface AskPayload {
  answer: string;
  citations: Array<{
    file_path: string;
    line_start: number;
    line_end: number;
    reason: string;
  }>;
  suggested_files: string[];
  confidence: string;
  limitations: string[];
  starter_questions?: string[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: unknown;
  };
}
