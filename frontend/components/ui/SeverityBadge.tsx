import { cn } from "@/lib/utils";
import type { Severity } from "@/types/api";

const CFG: Record<Severity, { bg: string; text: string; label: string }> = {
  critical: { bg: "bg-red-500/10 border-red-500/20",     text: "text-red-400",    label: "Critical" },
  high:     { bg: "bg-orange-500/10 border-orange-500/20", text: "text-orange-400", label: "High" },
  medium:   { bg: "bg-yellow-500/10 border-yellow-500/20", text: "text-yellow-400", label: "Medium" },
  low:      { bg: "bg-teal-500/10 border-teal-500/20",   text: "text-teal-400",   label: "Low" },
};

interface SeverityBadgeProps {
  severity: Severity | string;
  size?: "sm" | "md";
}

export default function SeverityBadge({ severity, size = "md" }: SeverityBadgeProps) {
  const cfg = CFG[severity as Severity] ?? {
    bg: "bg-gray-500/10 border-gray-500/20",
    text: "text-gray-400",
    label: severity,
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border font-medium",
        cfg.bg,
        cfg.text,
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
      )}
    >
      {cfg.label}
    </span>
  );
}
