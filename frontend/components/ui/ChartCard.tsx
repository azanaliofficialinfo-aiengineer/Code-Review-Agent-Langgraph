interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Chart area height in px (default 240) */
  height?: number;
}

export default function ChartCard({
  title,
  subtitle,
  children,
  height = 240,
}: ChartCardProps) {
  return (
    <div className="rounded-xl border border-white/6 bg-white/[0.025] p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-200">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p>}
      </div>
      <div style={{ height }}>{children}</div>
    </div>
  );
}
