"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  suffix?: string;
  description?: string;
  accent?: "blue" | "violet" | "emerald" | "red" | "orange" | "amber";
  animate?: boolean;
}

const ACCENT_MAP = {
  blue: {
    icon: "bg-blue-500/10 text-blue-400 border-blue-500/15",
    glow: "hover:shadow-blue-500/10",
    border: "hover:border-blue-500/20",
  },
  violet: {
    icon: "bg-violet-500/10 text-violet-400 border-violet-500/15",
    glow: "hover:shadow-violet-500/10",
    border: "hover:border-violet-500/20",
  },
  emerald: {
    icon: "bg-emerald-500/10 text-emerald-400 border-emerald-500/15",
    glow: "hover:shadow-emerald-500/10",
    border: "hover:border-emerald-500/20",
  },
  red: {
    icon: "bg-red-500/10 text-red-400 border-red-500/15",
    glow: "hover:shadow-red-500/10",
    border: "hover:border-red-500/20",
  },
  orange: {
    icon: "bg-orange-500/10 text-orange-400 border-orange-500/15",
    glow: "hover:shadow-orange-500/10",
    border: "hover:border-orange-500/20",
  },
  amber: {
    icon: "bg-amber-500/10 text-amber-400 border-amber-500/15",
    glow: "hover:shadow-amber-500/10",
    border: "hover:border-amber-500/20",
  },
};

function useCountUp(target: number, duration = 900): number {
  const [current, setCurrent] = useState(0);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    if (target === 0) { setCurrent(0); return; }
    const start = performance.now();

    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(eased * target));
      if (progress < 1) frameRef.current = requestAnimationFrame(tick);
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, duration]);

  return current;
}

export default function MetricCard({
  title,
  value,
  icon,
  suffix = "",
  description,
  accent = "blue",
  animate = true,
}: MetricCardProps) {
  const colors = ACCENT_MAP[accent];
  const numericValue = typeof value === "number" ? value : parseFloat(String(value));
  const displayNumber = useCountUp(
    isNaN(numericValue) ? 0 : numericValue,
    animate ? 900 : 0,
  );

  const displayValue =
    typeof value === "string" && isNaN(numericValue)
      ? value
      : `${displayNumber.toLocaleString()}${suffix}`;

  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-xl border border-white/6 bg-white/[0.03] p-5",
        "transition-all duration-300 hover:-translate-y-0.5 hover:bg-white/[0.05]",
        "hover:shadow-lg hover:shadow-black/30",
        colors.border,
        colors.glow,
      )}
    >
      {/* Header row */}
      <div className="mb-4 flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
          {title}
        </p>
        <div
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg border",
            colors.icon,
          )}
        >
          {icon}
        </div>
      </div>

      {/* Value */}
      <p className="text-2xl font-bold tabular-nums text-white">
        {displayValue}
      </p>

      {/* Description */}
      {description && (
        <p className="mt-1.5 text-xs text-gray-500">{description}</p>
      )}

      {/* Subtle gradient flare on hover */}
      <div className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-current opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-[0.04]" />
    </div>
  );
}
