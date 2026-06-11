"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { DailyRisk } from "@/types/api";

interface Props {
  data: DailyRisk[];
}

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  const score = payload[0].value;
  const color = score >= 70 ? "#ef4444" : score >= 40 ? "#f97316" : score >= 20 ? "#eab308" : "#10b981";
  return (
    <div className="rounded-lg border border-white/10 bg-[#0d0d1a]/95 px-3 py-2.5 text-xs shadow-xl backdrop-blur">
      <p className="mb-1 text-gray-400">
        {label ? format(parseISO(label), "MMM d, yyyy") : label}
      </p>
      <p className="font-bold" style={{ color }}>
        Risk score: {score}
      </p>
    </div>
  );
};

export default function RiskTrendChart({ data }: Props) {
  const formatted = data.map((d) => ({
    ...d,
    shortDate: format(parseISO(d.date), "MMM d"),
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={formatted} margin={{ top: 4, right: 4, bottom: 0, left: -8 }}>
        <defs>
          <linearGradient id="riskLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#a855f7" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
        <XAxis
          dataKey="shortDate"
          tick={{ fill: "#6b7280", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[0, 100]}
          ticks={[0, 25, 50, 75, 100]}
          tick={{ fill: "#6b7280", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <ReferenceLine y={50} stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone"
          dataKey="average_severity_score"
          stroke="url(#riskLine)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#a855f7", strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
