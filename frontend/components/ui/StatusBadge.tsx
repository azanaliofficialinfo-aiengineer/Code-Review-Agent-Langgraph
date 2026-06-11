import { cn } from "@/lib/utils";
import type { ReviewStatus } from "@/types/api";

const STATUS_CONFIG: Record<
  ReviewStatus,
  { label: string; dot: string; bg: string; text: string; pulse?: boolean }
> = {
  queued: {
    label: "Queued",
    dot: "bg-gray-400",
    bg: "bg-gray-500/10",
    text: "text-gray-400",
    border: "border-gray-500/20",
  } as never,
  fetching_context: {
    label: "Fetching",
    dot: "bg-blue-400",
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    pulse: true,
  } as never,
  reviewing: {
    label: "Reviewing",
    dot: "bg-yellow-400",
    bg: "bg-yellow-500/10",
    text: "text-yellow-400",
    pulse: true,
  } as never,
  completed: {
    label: "Completed",
    dot: "bg-emerald-400",
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
  } as never,
  failed: {
    label: "Failed",
    dot: "bg-red-400",
    bg: "bg-red-500/10",
    text: "text-red-400",
  } as never,
};

interface StatusBadgeProps {
  status: ReviewStatus | string;
  size?: "sm" | "md";
}

export default function StatusBadge({ status, size = "md" }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status as ReviewStatus] ?? {
    label: status,
    dot: "bg-gray-400",
    bg: "bg-gray-500/10",
    text: "text-gray-400",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        cfg.bg,
        cfg.text,
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
        "border-current/20",
      )}
    >
      <span className="relative flex h-1.5 w-1.5">
        {(cfg as { pulse?: boolean }).pulse && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              cfg.dot,
            )}
          />
        )}
        <span className={cn("relative inline-flex h-1.5 w-1.5 rounded-full", cfg.dot)} />
      </span>
      {cfg.label}
    </span>
  );
}
