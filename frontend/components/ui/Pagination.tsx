"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaginationProps {
  /** 0-indexed current page */
  page: number;
  totalPages: number;
  /** Total item count — when provided, renders "Showing X–Y of Z" */
  total?: number;
  pageSize?: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export default function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  className,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const showRange = total != null && pageSize != null;
  const rangeStart = page * (pageSize ?? 0) + 1;
  const rangeEnd = Math.min((page + 1) * (pageSize ?? 0), total ?? 0);

  return (
    <div className={cn("flex items-center justify-between text-sm text-gray-500", className)}>
      {showRange ? (
        <span>
          Showing {rangeStart}–{rangeEnd} of {total}
        </span>
      ) : (
        <span />
      )}

      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(Math.max(0, page - 1))}
          disabled={page === 0}
          aria-label="Previous page"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/6 text-gray-400 transition-colors hover:border-white/15 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-30"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="px-3 text-gray-400">
          {page + 1} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
          disabled={page >= totalPages - 1}
          aria-label="Next page"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/6 text-gray-400 transition-colors hover:border-white/15 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-30"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
