"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Database, GitPullRequest, Clock, CheckCircle2, Circle } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";
import Pagination from "@/components/ui/Pagination";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { getRepositories } from "@/lib/api";
import type { RepositoryListItem } from "@/types/api";
import { formatDistanceToNow } from "date-fns";

const PAGE_SIZE = 20;

export default function RepositoriesPage() {
  const [items,   setItems]   = useState<RepositoryListItem[]>([]);
  const [total,   setTotal]   = useState(0);
  const [page,    setPage]    = useState(0);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getRepositories({ limit: PAGE_SIZE, offset: page * PAGE_SIZE });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load repositories");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-5 animate-fade-up">
      <div>
        <h2 className="text-xl font-bold text-white">Repositories</h2>
        <p className="mt-0.5 text-sm text-gray-500">
          {loading ? "Loading…" : `${total} repositor${total === 1 ? "y" : "ies"} monitored`}
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Cards grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-white/6 bg-white/[0.025] p-5">
                <Skeleton className="mb-3 h-4 w-48" />
                <Skeleton className="mb-2 h-3 w-24" />
                <Skeleton className="h-3 w-32" />
              </div>
            ))
          : items.map((repo) => (
              <Link
                key={repo.full_name}
                href={`/repositories/${repo.owner}/${repo.name}`}
                className="group rounded-xl border border-white/6 bg-white/[0.025] p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-500/20 hover:bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/8 bg-white/3">
                      <Database className="h-4 w-4 text-violet-400" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500">{repo.owner}</p>
                      <p className="truncate font-semibold text-gray-200 transition-colors group-hover:text-blue-300">
                        {repo.name}
                      </p>
                    </div>
                  </div>
                  {repo.is_active ? (
                    <span className="flex shrink-0 items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/8 px-2 py-0.5 text-[10px] text-emerald-400">
                      <CheckCircle2 className="h-3 w-3" /> Active
                    </span>
                  ) : (
                    <span className="flex shrink-0 items-center gap-1 rounded-full border border-white/8 bg-white/3 px-2 py-0.5 text-[10px] text-gray-500">
                      <Circle className="h-3 w-3" /> Inactive
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span className="flex items-center gap-1.5">
                    <GitPullRequest className="h-3.5 w-3.5 text-blue-400" />
                    {repo.total_reviews} review{repo.total_reviews !== 1 ? "s" : ""}
                  </span>
                  {repo.last_review_at && (
                    <span className="flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5" />
                      {formatDistanceToNow(new Date(repo.last_review_at), { addSuffix: true })}
                    </span>
                  )}
                </div>
              </Link>
            ))}
      </div>

      {!loading && items.length === 0 && !error && (
        <EmptyState
          icon={<Database className="h-6 w-6" />}
          title="No repositories yet"
          description="Repositories will appear here once your GitHub App processes its first pull request event."
        />
      )}

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        className="justify-end"
      />
    </div>
  );
}
