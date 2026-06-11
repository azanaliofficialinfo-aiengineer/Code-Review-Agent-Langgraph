/**
 * Typed API client for the CodeReview Agent backend.
 *
 * Reads configuration from:
 *   NEXT_PUBLIC_API_URL          — backend base URL (default: http://localhost:8000)
 *   NEXT_PUBLIC_API_AUTH_TOKEN   — optional bearer token for protected endpoints
 */
import type {
  AnalyticsOverview,
  ReviewsPerDayResponse,
  SeverityDistribution,
  VerdictDistribution,
  RiskTrendResponse,
  PaginatedResponse,
  ReviewListItem,
  ReviewDetail,
  RepositoryListItem,
  WorkerStatusResponse,
} from "@/types/api";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = process.env.NEXT_PUBLIC_API_AUTH_TOKEN;
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { ...buildHeaders(), ...(init?.headers as Record<string, string> ?? {}) },
    // Disable Next.js caching for live dashboard data
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

// ── Worker ────────────────────────────────────────────────────────────────────

// No auth required — monitoring systems need liveness without credentials.
export const getWorkerStatus = (): Promise<WorkerStatusResponse> =>
  apiFetch<WorkerStatusResponse>("/reviews/worker/status");

// ── Analytics ─────────────────────────────────────────────────────────────────

export const getAnalyticsOverview = (): Promise<AnalyticsOverview> =>
  apiFetch<AnalyticsOverview>("/analytics/overview");

export const getReviewsPerDay = (days = 14): Promise<ReviewsPerDayResponse> =>
  apiFetch<ReviewsPerDayResponse>(`/analytics/reviews-per-day?days=${days}`);

export const getSeverityDistribution = (): Promise<SeverityDistribution> =>
  apiFetch<SeverityDistribution>("/analytics/severity-distribution");

export const getVerdictDistribution = (): Promise<VerdictDistribution> =>
  apiFetch<VerdictDistribution>("/analytics/verdict-distribution");

export const getRiskTrend = (days = 14): Promise<RiskTrendResponse> =>
  apiFetch<RiskTrendResponse>(`/analytics/risk-trend?days=${days}`);

// ── Reviews ───────────────────────────────────────────────────────────────────

export function getReviews(params?: {
  limit?: number;
  offset?: number;
  status?: string;
  repository?: string;
}): Promise<PaginatedResponse<ReviewListItem>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  if (params?.status) q.set("status", params.status);
  if (params?.repository) q.set("repository", params.repository);
  const qs = q.size ? `?${q}` : "";
  return apiFetch<PaginatedResponse<ReviewListItem>>(`/reviews${qs}`);
}

export function getReviewDetail(
  deliveryId: string,
  params?: { findings_limit?: number; findings_offset?: number },
): Promise<ReviewDetail> {
  const q = new URLSearchParams();
  if (params?.findings_limit != null) q.set("findings_limit", String(params.findings_limit));
  if (params?.findings_offset != null) q.set("findings_offset", String(params.findings_offset));
  const qs = q.size ? `?${q}` : "";
  return apiFetch<ReviewDetail>(`/reviews/${deliveryId}${qs}`);
}

// ── Repositories ──────────────────────────────────────────────────────────────

export function getRepositories(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<RepositoryListItem>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.size ? `?${q}` : "";
  return apiFetch<PaginatedResponse<RepositoryListItem>>(`/repositories${qs}`);
}

export function getRepositoryReviews(
  owner: string,
  repo: string,
  params?: { limit?: number; offset?: number },
): Promise<PaginatedResponse<ReviewListItem>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.size ? `?${q}` : "";
  return apiFetch<PaginatedResponse<ReviewListItem>>(
    `/repositories/${owner}/${repo}/reviews${qs}`,
  );
}
