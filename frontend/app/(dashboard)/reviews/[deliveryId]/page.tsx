"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  GitBranch,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  FileCode,
  Clock,
  Cpu,
} from "lucide-react";
import StatusBadge from "@/components/ui/StatusBadge";
import RiskBadge from "@/components/ui/RiskBadge";
import SeverityBadge from "@/components/ui/SeverityBadge";
import EmptyState from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { getReviewDetail } from "@/lib/api";
import type { ReviewDetail, Finding } from "@/types/api";
import { format } from "date-fns";

const FINDINGS_PAGE_SIZE = 20;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/6 bg-white/[0.025]">
      <div className="border-b border-white/5 px-5 py-3.5">
        <h3 className="text-sm font-semibold text-gray-200">{title}</h3>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function DataRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-4 py-2 border-b border-white/3 last:border-0">
      <span className="w-36 shrink-0 text-xs text-gray-500">{label}</span>
      <span className="text-sm text-gray-200">{children}</span>
    </div>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const [expanded, setExpanded] = useState(false);

  function toggle() { setExpanded((e) => !e); }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      aria-label={`${finding.severity} finding: ${finding.title}`}
      className="cursor-pointer rounded-lg border border-white/5 bg-white/[0.02] p-4 transition-all hover:border-white/10 hover:bg-white/[0.04] focus:outline-none focus:ring-1 focus:ring-blue-500/30"
      onClick={toggle}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      }}
    >
      <div className="flex items-start gap-3">
        <SeverityBadge severity={finding.severity} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-gray-200 text-sm">{finding.title}</p>
            <span className="text-xs text-gray-600 bg-white/5 rounded px-1.5 py-0.5">
              {finding.category}
            </span>
          </div>
          <p className="mt-1 text-xs text-gray-500 font-mono">
            {finding.file_path}
            {finding.line != null && <span className="text-gray-600">:{finding.line}</span>}
          </p>
          {expanded && (
            <div className="mt-3 space-y-2.5">
              <div>
                <p className="text-xs font-medium text-gray-400 mb-1">Description</p>
                <p className="text-sm text-gray-300 leading-relaxed">{finding.description}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-400 mb-1">Suggestion</p>
                <p className="text-sm text-gray-300 leading-relaxed">{finding.suggestion}</p>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>Confidence: {(finding.confidence * 100).toFixed(0)}%</span>
                <span>Will comment: {finding.should_comment ? "Yes" : "No"}</span>
              </div>
            </div>
          )}
        </div>
        <span className="text-xs text-gray-600 shrink-0">{expanded ? "▲" : "▼"}</span>
      </div>
    </div>
  );
}

export default function ReviewDetailPage() {
  const params = useParams();
  const router = useRouter();
  const deliveryId = params.deliveryId as string;

  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [findingsPage, setFindingsPage] = useState(0);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const d = await getReviewDetail(deliveryId, {
          findings_limit: FINDINGS_PAGE_SIZE,
          findings_offset: findingsPage * FINDINGS_PAGE_SIZE,
        });
        setDetail(d);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load review");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [deliveryId, findingsPage]);

  if (loading) {
    return (
      <div className="space-y-5 animate-fade-up">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-5 lg:grid-cols-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-white/6 bg-white/[0.025] p-5">
              <Skeleton className="mb-3 h-4 w-32" />
              {Array.from({ length: 4 }).map((_, j) => (
                <Skeleton key={j} className="mb-2 h-3 w-full" />
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-5">
        <button onClick={() => router.back()} className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4" /> {error}
        </div>
      </div>
    );
  }

  if (!detail) return null;

  const { pull_request: pr, repository: repo, summary, findings, submission } = detail;
  const findingsTotalPages = Math.ceil(findings.total / FINDINGS_PAGE_SIZE);

  return (
    <div className="space-y-5 animate-fade-up">
      {/* Back button */}
      <Link href="/reviews" className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200 transition-colors">
        <ArrowLeft className="h-4 w-4" /> All Reviews
      </Link>

      {/* PR Header */}
      <div className="rounded-xl border border-white/6 bg-white/[0.025] p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <span className="text-xs font-mono text-gray-500">{repo.full_name}</span>
              <span className="text-gray-600">·</span>
              <span className="text-xs text-gray-500">PR #{pr.pr_number}</span>
              <StatusBadge status={detail.status} />
            </div>
            <h2 className="text-lg font-bold text-white">
              {pr.title ?? `Pull Request #${pr.pr_number}`}
            </h2>
            {pr.author && (
              <p className="mt-1 text-sm text-gray-500">by {pr.author}</p>
            )}
          </div>
          {pr.html_url && (
            <a
              href={pr.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-lg border border-white/8 bg-white/3 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors shrink-0"
            >
              GitHub <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>

        {/* Branch info */}
        {(pr.base_branch || pr.head_branch) && (
          <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
            <GitBranch className="h-3.5 w-3.5" />
            <span className="font-mono">{pr.base_branch}</span>
            <span className="text-gray-700">←</span>
            <span className="font-mono text-blue-400">{pr.head_branch}</span>
          </div>
        )}
      </div>

      {/* Summary + Job meta in 2 cols */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Review summary */}
        <Section title="Review Summary">
          {summary ? (
            <div>
              <div className="mb-4 flex items-center gap-3 flex-wrap">
                <RiskBadge value={summary.verdict} variant="verdict" />
                <RiskBadge value={summary.risk_level} />
                <span className="rounded-lg border border-white/8 bg-white/3 px-2.5 py-1 text-xs font-mono text-gray-300">
                  Score: {summary.severity_score}/100
                </span>
              </div>
              <p className="mb-4 text-sm leading-relaxed text-gray-300">{summary.summary_text}</p>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: "Critical", count: summary.critical_count, color: "text-red-400" },
                  { label: "High",     count: summary.high_count,     color: "text-orange-400" },
                  { label: "Medium",   count: summary.medium_count,   color: "text-yellow-400" },
                  { label: "Low",      count: summary.low_count,      color: "text-teal-400" },
                ].map(({ label, count, color }) => (
                  <div key={label} className="rounded-lg border border-white/5 bg-white/3 p-3 text-center">
                    <p className={`text-xl font-bold tabular-nums ${color}`}>{count}</p>
                    <p className="text-[10px] text-gray-500">{label}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500">No summary available — review may not be complete.</p>
          )}
        </Section>

        {/* Job metadata */}
        <Section title="Job Details">
          <DataRow label="Delivery ID">
            <span className="font-mono text-xs text-gray-400 break-all">{detail.delivery_id}</span>
          </DataRow>
          <DataRow label="Provider">
            <span className="flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-violet-400" />
              {detail.provider ?? "—"} · {detail.model ?? "—"}
            </span>
          </DataRow>
          <DataRow label="Duration">
            <span className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-blue-400" />
              {detail.duration_ms ? `${(detail.duration_ms / 1000).toFixed(1)}s` : "—"}
            </span>
          </DataRow>
          {detail.started_at && (
            <DataRow label="Started">
              {format(new Date(detail.started_at), "MMM d, yyyy HH:mm:ss")}
            </DataRow>
          )}
          {detail.completed_at && (
            <DataRow label="Completed">
              {format(new Date(detail.completed_at), "MMM d, yyyy HH:mm:ss")}
            </DataRow>
          )}
          {detail.error_message && (
            <DataRow label="Error">
              <span className="text-red-400 text-xs">{detail.error_message}</span>
            </DataRow>
          )}
        </Section>
      </div>

      {/* Findings */}
      <Section title={`Findings (${findings.total})`}>
        {findings.items.length === 0 ? (
          <EmptyState
            icon={<FileCode className="h-6 w-6" />}
            title="No findings"
            description="This review found no issues, or the review is not yet complete."
            className="border-0 py-8"
          />
        ) : (
          <div className="space-y-2">
            {findings.items.map((f, i) => (
              <FindingCard key={i} finding={f} />
            ))}
          </div>
        )}

        {findingsTotalPages > 1 && (
          <div className="mt-4 flex items-center justify-between text-sm text-gray-500">
            <span>
              {findingsPage * FINDINGS_PAGE_SIZE + 1}–
              {Math.min((findingsPage + 1) * FINDINGS_PAGE_SIZE, findings.total)} of{" "}
              {findings.total}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setFindingsPage((p) => Math.max(0, p - 1))}
                disabled={findingsPage === 0}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/6 hover:border-white/15 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-3 text-gray-400">
                {findingsPage + 1} / {findingsTotalPages}
              </span>
              <button
                onClick={() => setFindingsPage((p) => Math.min(findingsTotalPages - 1, p + 1))}
                disabled={findingsPage >= findingsTotalPages - 1}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/6 hover:border-white/15 disabled:opacity-30 transition-colors"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </Section>

      {/* Submission */}
      {submission && (
        <Section title="Review Submission">
          <div className="grid gap-4 sm:grid-cols-2">
            <DataRow label="Event">{submission.event}</DataRow>
            <DataRow label="Inline Comments">{submission.inline_comment_count}</DataRow>
            <DataRow label="Dry Run">
              <span className={submission.dry_run ? "text-yellow-400" : "text-emerald-400"}>
                {submission.dry_run ? "Yes (not posted to GitHub)" : "No"}
              </span>
            </DataRow>
            <DataRow label="Submitted to GitHub">
              <span className={submission.submitted_to_github ? "text-emerald-400" : "text-gray-500"}>
                {submission.submitted_to_github ? "Yes" : "No"}
              </span>
            </DataRow>
            {submission.github_review_id && (
              <DataRow label="GitHub Review ID">
                <span className="font-mono text-xs text-gray-400">{submission.github_review_id}</span>
              </DataRow>
            )}
            <DataRow label="Commit">
              <span className="font-mono text-xs text-gray-400">{submission.commit_id.slice(0, 10)}</span>
            </DataRow>
          </div>
        </Section>
      )}
    </div>
  );
}
