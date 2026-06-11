"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Database,
  GitPullRequest,
  AlertTriangle,
  Clock,
  CheckCircle2,
} from "lucide-react";
import StatusBadge from "@/components/ui/StatusBadge";
import RiskBadge from "@/components/ui/RiskBadge";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { getRepositoryReviews } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import type { ReviewListItem } from "@/types/api";
import { format, formatDistanceToNow } from "date-fns";

const PAGE_SIZE = 20;

export default function RepositoryDetailPage() {
  const params   = useParams();
  const router   = useRouter();
  const owner    = params.owner as string;
  const repo     = params.repo  as string;

  const [items,   setItems]   = useState<ReviewListItem[]>([]);
  const [total,   setTotal]   = useState(0);
  const [page,    setPage]    = useState(0);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getRepositoryReviews(owner, repo, {
        limit:  PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load repository reviews");
    } finally {
      setLoading(false);
    }
  }, [owner, repo, page]);

  useEffect(() => { load(); }, [load]);

  const totalPages  = Math.ceil(total / PAGE_SIZE);
  const lastReview  = items[0]?.created_at;

  function navigateTo(deliveryId: string) {
    router.push(`/reviews/${deliveryId}`);
  }

  return (
    <div className="space-y-5 animate-fade-up">
      {/* Back */}
      <Link
        href="/repositories"
        className="inline-flex items-center gap-2 text-sm text-gray-400 transition-colors hover:text-gray-200"
      >
        <ArrowLeft className="h-4 w-4" /> All Repositories
      </Link>

      {/* Repo header */}
      <div className="rounded-xl border border-white/6 bg-white/[0.025] p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-violet-500/20 bg-violet-500/8">
            <Database className="h-5 w-5 text-violet-400" />
          </div>
          <div>
            <p className="text-xs text-gray-500">{owner}</p>
            <h2 className="text-lg font-bold text-white">{repo}</h2>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-5 text-xs text-gray-500">
          <span className="flex items-center gap-1.5">
            <GitPullRequest className="h-3.5 w-3.5 text-blue-400" />
            {total} review{total !== 1 ? "s" : ""}
          </span>
          {lastReview && (
            <span className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              Last review {formatDistanceToNow(new Date(lastReview), { addSuffix: true })}
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            {items.filter((r) => r.status === "completed").length} completed
          </span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Reviews table */}
      <div className="overflow-hidden rounded-xl border border-white/6 bg-white/[0.025]">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-left">
                {["PR", "Title", "Status", "Verdict", "Risk", "Score", "Duration", "Created"].map((h) => (
                  <th key={h} className="whitespace-nowrap px-4 py-3 text-xs font-medium text-gray-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/3">
              {loading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="border-b border-white/3">
                      {Array.from({ length: 8 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-3.5 w-full max-w-[90px]" />
                        </td>
                      ))}
                    </tr>
                  ))
                : items.map((r) => (
                    <tr
                      key={r.delivery_id}
                      role="button"
                      tabIndex={0}
                      aria-label={`View review for PR #${r.pr_number}`}
                      className="group cursor-pointer transition-colors hover:bg-white/[0.025] focus:outline-none focus:bg-white/[0.025] focus:ring-1 focus:ring-inset focus:ring-blue-500/20"
                      onClick={() => navigateTo(r.delivery_id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          navigateTo(r.delivery_id);
                        }
                      }}
                    >
                      <td className="px-4 py-3 font-medium text-blue-400">#{r.pr_number}</td>
                      <td className="max-w-[200px] px-4 py-3">
                        <span className="block truncate text-gray-300" title={r.title ?? ""}>
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
                      <td className="px-4 py-3 tabular-nums text-gray-400">
                        {r.severity_score ?? "—"}
                      </td>
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
            title="No reviews for this repository"
            description="Reviews will appear here once pull requests are processed."
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
