"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { GitPullRequest, Search, Clock } from "lucide-react";
import StatusBadge from "@/components/ui/StatusBadge";
import RiskBadge from "@/components/ui/RiskBadge";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { getReviews } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import type { ReviewListItem, ReviewStatus } from "@/types/api";
import { format } from "date-fns";

const STATUSES: { value: ReviewStatus | ""; label: string }[] = [
  { value: "",                label: "All statuses" },
  { value: "queued",          label: "Queued" },
  { value: "fetching_context",label: "Fetching" },
  { value: "reviewing",       label: "Reviewing" },
  { value: "completed",       label: "Completed" },
  { value: "failed",          label: "Failed" },
];

const PAGE_SIZE = 20;

export default function ReviewsPage() {
  const router = useRouter();

  const [items,       setItems]       = useState<ReviewListItem[]>([]);
  const [total,       setTotal]       = useState(0);
  const [page,        setPage]        = useState(0);
  const [status,      setStatus]      = useState<ReviewStatus | "">("");
  const [repoFilter,  setRepoFilter]  = useState("");
  const [inputValue,  setInputValue]  = useState("");
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getReviews({
        limit:      PAGE_SIZE,
        offset:     page * PAGE_SIZE,
        status:     status     || undefined,
        repository: repoFilter || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load reviews");
    } finally {
      setLoading(false);
    }
  }, [page, status, repoFilter]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  function handleSearch() {
    setRepoFilter(inputValue.trim());
    setPage(0);
  }

  function navigateTo(deliveryId: string) {
    router.push(`/reviews/${deliveryId}`);
  }

  return (
    <div className="space-y-5 animate-fade-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Reviews</h2>
          <p className="mt-0.5 text-sm text-gray-500">
            {loading ? "Loading…" : `${total.toLocaleString()} total review jobs`}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          {/* sr-only label satisfies accessibility without cluttering the UI */}
          <label htmlFor="repo-filter" className="sr-only">
            Filter by repository
          </label>
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-500" />
          <input
            id="repo-filter"
            type="text"
            placeholder="Filter by repository…"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="h-9 w-56 rounded-lg border border-white/8 bg-white/3 pl-9 pr-4 text-sm text-gray-200 placeholder-gray-600 outline-none transition-colors focus:border-blue-500/40 focus:bg-white/5"
          />
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value as ReviewStatus | ""); setPage(0); }}
          aria-label="Filter by status"
          className="h-9 cursor-pointer rounded-lg border border-white/8 bg-white/3 px-3 text-sm text-gray-300 outline-none transition-colors focus:border-blue-500/40"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value} className="bg-gray-900">
              {s.label}
            </option>
          ))}
        </select>
        {(repoFilter || status) && (
          <button
            onClick={() => { setRepoFilter(""); setInputValue(""); setStatus(""); setPage(0); }}
            className="h-9 rounded-lg border border-white/8 bg-white/3 px-3 text-sm text-gray-400 transition-colors hover:text-gray-200"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-white/6 bg-white/[0.025]">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-left">
                {["Repository", "PR", "Title", "Status", "Verdict", "Risk", "Provider", "Duration", "Created"].map((h) => (
                  <th key={h} className="whitespace-nowrap px-4 py-3 text-xs font-medium text-gray-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/3">
              {loading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-white/3">
                      {Array.from({ length: 9 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-3.5 w-full max-w-[100px]" />
                        </td>
                      ))}
                    </tr>
                  ))
                : items.map((r) => (
                    <tr
                      key={r.delivery_id}
                      role="button"
                      tabIndex={0}
                      aria-label={`View review: ${r.repository} PR #${r.pr_number}`}
                      className="group cursor-pointer transition-colors hover:bg-white/[0.025] focus:outline-none focus:bg-white/[0.025] focus:ring-1 focus:ring-inset focus:ring-blue-500/20"
                      onClick={() => navigateTo(r.delivery_id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          navigateTo(r.delivery_id);
                        }
                      }}
                    >
                      <td className="px-4 py-3">
                        <span className="font-medium text-gray-200 transition-colors group-hover:text-blue-400">
                          {r.repository}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400">#{r.pr_number}</td>
                      <td className="max-w-[180px] px-4 py-3">
                        <span className="block truncate text-gray-400" title={r.title ?? ""}>
                          {r.title ?? "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3"><StatusBadge status={r.status} size="sm" /></td>
                      <td className="px-4 py-3">
                        {r.verdict
                          ? <RiskBadge value={r.verdict} variant="verdict" size="sm" />
                          : <span className="text-gray-600">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        {r.risk_level
                          ? <RiskBadge value={r.risk_level} size="sm" />
                          : <span className="text-gray-600">—</span>}
                      </td>
                      <td className="px-4 py-3 text-gray-500">{r.provider ?? "—"}</td>
                      <td className="px-4 py-3 tabular-nums text-gray-500">
                        {formatDuration(r.duration_ms)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-1 whitespace-nowrap text-gray-500">
                          <Clock className="h-3 w-3" />
                          {format(new Date(r.created_at), "MMM d, HH:mm")}
                        </span>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>

        {!loading && items.length === 0 && !error && (
          <EmptyState
            icon={<GitPullRequest className="h-6 w-6" />}
            title="No reviews found"
            description={
              repoFilter || status
                ? "Try adjusting your filters."
                : "Reviews will appear here once your GitHub App starts receiving events."
            }
            className="rounded-none border-0"
          />
        )}
      </div>

      <Pagination
        page={page}
        totalPages={totalPages}
        total={total}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
      />
    </div>
  );
}
