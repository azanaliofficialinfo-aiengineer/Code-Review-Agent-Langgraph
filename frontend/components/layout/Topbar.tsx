"use client";

import { usePathname } from "next/navigation";
import { ExternalLink, Menu } from "lucide-react";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard":     "Overview",
  "/reviews":       "Reviews",
  "/repositories":  "Repositories",
};

function getTitle(pathname: string): string {
  if (pathname.startsWith("/reviews/")) return "Review Detail";
  if (pathname.startsWith("/repositories/")) {
    const parts = pathname.split("/").filter(Boolean);
    if (parts.length >= 3) return `${parts[1]}/${parts[2]}`;
    return "Repository";
  }
  return PAGE_TITLES[pathname] ?? "Dashboard";
}

interface TopbarProps {
  onMenuClick?: () => void;
}

export default function Topbar({ onMenuClick }: TopbarProps) {
  const pathname = usePathname();
  const title    = getTitle(pathname);
  const apiUrl   = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-white/5 bg-[#080810]/80 px-4 backdrop-blur-xl lg:px-6">
      <div className="flex items-center gap-3">
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuClick}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/8 text-gray-400 transition-colors hover:border-white/15 hover:text-gray-200 lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-4 w-4" />
        </button>
        <h1 className="text-sm font-semibold text-white">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        {/* Live indicator */}
        <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/8 px-2.5 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          <span className="text-xs font-medium text-emerald-400">Live</span>
        </div>

        <a
          href={`${apiUrl}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 rounded-lg border border-white/8 bg-white/3 px-3 py-1.5 text-xs font-medium text-gray-400 transition-all hover:border-white/15 hover:text-gray-200"
        >
          API
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </header>
  );
}
