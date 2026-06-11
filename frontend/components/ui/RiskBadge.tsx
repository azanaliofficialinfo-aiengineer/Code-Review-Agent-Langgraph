import { cn } from "@/lib/utils";
import type { RiskLevel, Verdict } from "@/types/api";

const RISK_CFG: Record<RiskLevel, { bg: string; text: string; label: string }> = {
  critical: { bg: "bg-red-500/10 border-red-500/20",       text: "text-red-400",    label: "Critical Risk" },
  high:     { bg: "bg-orange-500/10 border-orange-500/20", text: "text-orange-400", label: "High Risk" },
  medium:   { bg: "bg-yellow-500/10 border-yellow-500/20", text: "text-yellow-400", label: "Medium Risk" },
  low:      { bg: "bg-teal-500/10 border-teal-500/20",     text: "text-teal-400",   label: "Low Risk" },
};

const VERDICT_CFG: Record<Verdict, { bg: string; text: string; label: string }> = {
  approve:          { bg: "bg-emerald-500/10 border-emerald-500/20", text: "text-emerald-400", label: "Approve" },
  comment:          { bg: "bg-blue-500/10 border-blue-500/20",       text: "text-blue-400",    label: "Comment" },
  request_changes:  { bg: "bg-red-500/10 border-red-500/20",         text: "text-red-400",     label: "Request Changes" },
};

interface RiskBadgeProps {
  value: RiskLevel | string;
  variant?: "risk" | "verdict";
  size?: "sm" | "md";
}

export default function RiskBadge({ value, variant = "risk", size = "md" }: RiskBadgeProps) {
  const cfg =
    variant === "verdict"
      ? (VERDICT_CFG[value as Verdict] ?? { bg: "bg-gray-500/10 border-gray-500/20", text: "text-gray-400", label: value })
      : (RISK_CFG[value as RiskLevel] ?? { bg: "bg-gray-500/10 border-gray-500/20", text: "text-gray-400", label: value });

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
