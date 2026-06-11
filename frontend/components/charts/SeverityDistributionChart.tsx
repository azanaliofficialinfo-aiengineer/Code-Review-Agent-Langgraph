"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import type { SeverityDistribution } from "@/types/api";

interface Props {
  data: SeverityDistribution;
}

const COLORS = {
  Critical: "#ef4444",
  High: "#f97316",
  Medium: "#eab308",
  Low: "#14b8a6",
};

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) => {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  return (
    <div className="rounded-lg border border-white/10 bg-[#0d0d1a]/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <span className="font-medium text-gray-300">{p.name}: </span>
      <span className="font-bold text-white">{p.value}</span>
    </div>
  );
};

export default function SeverityDistributionChart({ data }: Props) {
  const chartData = [
    { name: "Critical", value: data.critical },
    { name: "High",     value: data.high },
    { name: "Medium",   value: data.medium },
    { name: "Low",      value: data.low },
  ].filter((d) => d.value > 0);

  const total = chartData.reduce((s, d) => s + d.value, 0);

  if (total === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2">
        <div className="h-24 w-24 rounded-full border-4 border-white/5" />
        <p className="text-sm text-gray-500">No findings yet</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="45%"
          innerRadius="55%"
          outerRadius="75%"
          paddingAngle={3}
          dataKey="value"
          strokeWidth={0}
        >
          {chartData.map((entry) => (
            <Cell key={entry.name} fill={COLORS[entry.name as keyof typeof COLORS]} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(v) => <span className="text-xs text-gray-400">{v}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
