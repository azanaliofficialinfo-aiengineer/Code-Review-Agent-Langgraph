// API response types — mirrors backend Pydantic schemas exactly.

export type ReviewStatus =
  | "queued"
  | "fetching_context"
  | "reviewing"
  | "completed"
  | "failed";

export type Severity = "critical" | "high" | "medium" | "low";
export type Verdict = "approve" | "comment" | "request_changes";
export type RiskLevel = "critical" | "high" | "medium" | "low";

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface AnalyticsOverview {
  total_reviews: number;
  total_repositories: number;
  completed_reviews: number;
  failed_reviews: number;
  success_rate: number;
  total_findings: number;
  critical_findings: number;
  high_findings: number;
  average_severity_score: number;
  average_duration_ms: number;
}

export interface DailyReview {
  date: string; // "YYYY-MM-DD"
  reviews: number;
  completed: number;
  failed: number;
}

export interface ReviewsPerDayResponse {
  items: DailyReview[];
}

export interface SeverityDistribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface VerdictDistribution {
  approve: number;
  comment: number;
  request_changes: number;
}

export interface DailyRisk {
  date: string;
  average_severity_score: number;
}

export interface RiskTrendResponse {
  items: DailyRisk[];
}

// ── Common ─────────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ── Reviews ───────────────────────────────────────────────────────────────────

export interface ReviewListItem {
  delivery_id: string;
  repository: string;
  pr_number: number;
  title: string | null;
  author: string | null;
  status: ReviewStatus;
  verdict: Verdict | null;
  risk_level: RiskLevel | null;
  severity_score: number | null;
  provider: string | null;
  model: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface Finding {
  file_path: string;
  line: number | null;
  severity: Severity;
  category: string;
  title: string;
  description: string;
  suggestion: string;
  confidence: number;
  should_comment: boolean;
}

export interface PaginatedFindingList {
  items: Finding[];
  total: number;
  limit: number;
  offset: number;
}

export interface RepositoryInfo {
  owner: string;
  name: string;
  full_name: string;
  installation_id: number;
  default_branch: string | null;
  is_active: boolean;
}

export interface PullRequestInfo {
  pr_number: number;
  title: string | null;
  author: string | null;
  base_branch: string | null;
  head_branch: string | null;
  base_sha: string | null;
  head_sha: string | null;
  html_url: string | null;
  state: string | null;
}

export interface SummaryInfo {
  verdict: Verdict;
  risk_level: RiskLevel;
  severity_score: number;
  summary_text: string;
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
}

export interface SubmissionInfo {
  event: string;
  commit_id: string;
  dry_run: boolean;
  submitted_to_github: boolean;
  inline_comment_count: number;
  github_review_id: number | null;
  created_at: string;
}

export interface ReviewDetail {
  delivery_id: string;
  status: ReviewStatus;
  provider: string | null;
  model: string | null;
  event_action: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
  repository: RepositoryInfo;
  pull_request: PullRequestInfo;
  summary: SummaryInfo | null;
  findings: PaginatedFindingList;
  submission: SubmissionInfo | null;
}

// ── Worker ────────────────────────────────────────────────────────────────────

export interface WorkerStatusResponse {
  status: "alive" | "dead" | "unknown";
  updated_at: string | null;
  last_heartbeat_ago_seconds: number | null;
}

// ── Repositories ──────────────────────────────────────────────────────────────

export interface RepositoryListItem {
  full_name: string;
  owner: string;
  name: string;
  installation_id: number;
  is_active: boolean;
  total_reviews: number;
  last_review_at: string | null;
}
