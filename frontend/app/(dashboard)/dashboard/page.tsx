"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  GitPullRequest,
  Database,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  ArrowRight,
  Clock,
} from "lucide-react";
import MetricCard from "@/components/ui/MetricCard";
import StatusBadge from "@/components/ui/StatusBadge";
import RiskBadge from "@/components/ui/RiskBadge";
import ChartCard from "@/components/ui/ChartCard";
import EmptyState from "@/components/ui/EmptyState";
import { MetricCardSkeleton, ChartSkeleton, Skeleton } from "@/components/ui/LoadingSkeleton";
import {
  getAnalyticsOverview,
  getReviewsPerDay,
  getSeverityDistribution,
  getVerdictDistribution,
  getRiskTrend,
  getReviews,
} from "@/lib/api";
import { formatDuration } from "@/lib/format";
import type {
  AnalyticsOverview,
  ReviewsPerDayResponse,
  SeverityDistribution,
  VerdictDistribution,
  RiskTrendResponse,
  ReviewListItem,
} from "@/types/api";
import { format } from "date-fns";

// Load charts as client-only (no SSR) to avoid hydration issues with recharts
const ReviewsPerDayChart = dynamic(
  () => import("@/components/charts/ReviewsPerDayChart"),
  { ssr: false, loading: () => <div className="h-full animate-pulse rounded-lg bg-white/3" /> },
);
const SeverityDistributionChart = dynamic(
  () => import("@/components/charts/SeverityDistributionChart"),
  { ssr: false, loading: () => <div className="h-full animate-pulse rounded-lg bg-white/3" /> },
);
const VerdictDistributionChart = dynamic(
  () => import("@/components/charts/VerdictDistributionChart"),
  { ssr: false, loading: () => <div className="h-full animate-pulse rounded-lg bg-white/3" /> },
);
const RiskTrendChart = dynamic(
  () => import("@/components/charts/RiskTrendChart"),
  { ssr: false, loading: () => <div className="h-full animate-pulse rounded-lg bg-white/3" /> },
);

export default function DashboardPage() {
  const router = useRouter();

  const [overview,       setOverview]       = useState<AnalyticsOverview | null>(null);
  const [perDay,         setPerDay]         = useState<ReviewsPerDayResponse | null>(null);
  const [severity,       setSeverity]       = useState<SeverityDistribution | null>(null);
  const [verdict,        setVerdict]        = useState<VerdictDistribution | null>(null);
  const [riskTrend,      setRiskTrend]      = useState<RiskTrendResponse | null>(null);
  const [recentReviews,  setRecentReviews]  = useState<ReviewListItem[]>([]);
  const [loading,        setLoading]        = useState(true);
  const [error,          setError]          = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [ov, pd, sev, ver, rt, rv] = await Promise.all([
          getAnalyticsOverview(),
          getReviewsPerDay(14),
          getSeverityDistribution(),
          getVerdictDistribution(),
          getRiskTrend(14),
          getReviews({ limit: 10, offset: 0 }),
        ]);
        setOverview(ov);
        setPerDay(pd);
        setSeverity(sev);
        setVerdict(ver);
        setRiskTrend(rt);
        setRecentReviews(rv.items);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Hero header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          Autonomous PR Review Intelligence
        </h2>
        <p className="mt-1.5 text-sm text-gray-500">
          LangGraph-powered code review automation with Groq AI, GitHub Reviews, and PostgreSQL analytics.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error} — check that the backend is running at {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</span>
        </div>
      )}

      {/* Metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => <MetricCardSkeleton key={i} />)
        ) : overview ? (
          <>
            <MetricCard title="Total Reviews"     value={overview.total_reviews}          icon={<GitPullRequest className="h-4 w-4" />} accent="blue"    description="All-time review jobs" />
            <MetricCard title="Repositories"      value={overview.total_repositories}     icon={<Database className="h-4 w-4" />}      accent="violet"  description="Active repositories" />
            <MetricCard title="Critical Findings" value={overview.critical_findings}      icon={<AlertTriangle className="h-4 w-4" />} accent="red"     description="Needs immediate attention" />
            <MetricCard title="Avg Risk Score"    value={overview.average_severity_score} icon={<TrendingUp className="h-4 w-4" />}    accent="orange"  description="0 = clean, 100 = critical" />
            <MetricCard title="Success Rate"      value={overview.success_rate}           icon={<CheckCircle2 className="h-4 w-4" />}  accent="emerald" suffix="%" description={`${overview.completed_reviews} completed`} />
            <MetricCard title="Failed Reviews"    value={overview.failed_reviews}         icon={<XCircle className="h-4 w-4" />}       accent="red"     description="Pipeline errors" />
          </>
        ) : null}
      </div>

      {/* Charts — 2×2 grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <ChartSkeleton key={i} />)
        ) : (
          <>
            <ChartCard title="Reviews Per Day" subtitle="Last 14 days · completed vs failed">
              {perDay && <ReviewsPerDayChart data={perDay.items} />}
            </ChartCard>
            <ChartCard title="Severity Distribution" subtitle="Findings by severity level">
              {severity && <SeverityDistributionChart data={severity} />}
            </ChartCard>
            <ChartCard title="Risk Trend" subtitle="Average severity score over time">
              {riskTrend && <RiskTrendChart data={riskTrend.items} />}
            </ChartCard>
            <ChartCard title="Verdict Distribution" subtitle="Review outcomes">
              {verdict && <VerdictDistributionChart data={verdict} />}
            </ChartCard>
          </>
        )}
      </div>

      {/* Recent reviews table */}
      <div className="rounded-xl border border-white/6 bg-white/[0.025]">
        <div className="flex items-center justify-between border-b border-white/5 px-5 py-4">
          <h3 className="text-sm font-semibold text-gray-200">Recent Reviews</h3>
          <Link
            href="/reviews"
            className="flex items-center gap-1.5 text-xs text-blue-400 transition-colors hover:text-blue-300"
          >
            View all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {loading ? (
          <div className="divide-y divide-white/4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-3">
                <Skeleton className="h-3 w-32" />
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="ml-auto h-3 w-24" />
              </div>
            ))}
          </div>
        ) : recentReviews.length === 0 ? (
          <EmptyState
            icon={<GitPullRequest className="h-6 w-6" />}
            title="No reviews yet"
            description="Reviews will appear here once your GitHub App starts receiving pull request events."
            className="rounded-none border-0"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/4 text-left">
                  {["Repository", "PR", "Status", "Verdict", "Risk", "Duration", "Created"].map((h) => (
                    <th key={h} className="px-5 py-2.5 text-xs font-medium text-gray-500">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/3">
                {recentReviews.map((r) => (
                  <tr
                    key={r.delivery_id}
                    role="button"
                    tabIndex={0}
                    aria-label={`View review: ${r.repository} PR #${r.pr_number}`}
                    className="group cursor-pointer transition-colors hover:bg-white/[0.025] focus:outline-none focus:bg-white/[0.025] focus:ring-1 focus:ring-inset focus:ring-blue-500/20"
                    onClick={() => router.push(`/reviews/${r.delivery_id}`)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        router.push(`/reviews/${r.delivery_id}`);
                      }
                    }}
                  >
                    <td className="px-5 py-3">
                      <span className="font-medium text-gray-200 group-hover:text-blue-300 transition-colors">
                        {r.repository}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-400">#{r.pr_number}</td>
                    <td className="px-5 py-3"><StatusBadge status={r.status} size="sm" /></td>
                    <td className="px-5 py-3">
                      {r.verdict
                        ? <RiskBadge value={r.verdict} variant="verdict" size="sm" />
                        : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-5 py-3">
                      {r.risk_level
                        ? <RiskBadge value={r.risk_level} size="sm" />
                        : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-gray-500">
                      {formatDuration(r.duration_ms)}
                    </td>
                    <td className="px-5 py-3">
                      <span className="flex items-center gap-1 text-gray-500">
                        <Clock className="h-3 w-3" />
                        {format(new Date(r.created_at), "MMM d, HH:mm")}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
