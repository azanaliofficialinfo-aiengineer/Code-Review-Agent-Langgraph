"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitPullRequest,
  Database,
  Zap,
  ExternalLink,
  Activity,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getWorkerStatus } from "@/lib/api";
import type { WorkerStatusResponse } from "@/types/api";

const navItems = [
  { href: "/dashboard",     label: "Overview",      icon: LayoutDashboard },
  { href: "/reviews",       label: "Reviews",       icon: GitPullRequest },
  { href: "/repositories",  label: "Repositories",  icon: Database },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-30 flex h-screen w-56 flex-col border-r border-white/5 bg-[#080810]/90 backdrop-blur-xl",
        "transition-transform duration-300 ease-in-out",
        // Desktop: always visible; mobile: slide in/out
        "-translate-x-full lg:translate-x-0",
        isOpen && "translate-x-0",
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 border-b border-white/5 px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 shadow-lg">
          <Zap className="h-3.5 w-3.5 text-white" />
        </div>
        <div>
          <span className="text-sm font-semibold text-white">CodeReview</span>
          <span className="ml-1 text-sm font-semibold text-blue-400">Agent</span>
        </div>

        {/* Close button — mobile only */}
        <button
          onClick={onClose}
          className="ml-auto flex h-7 w-7 items-center justify-center rounded-lg text-gray-500 transition-colors hover:text-gray-200 lg:hidden"
          aria-label="Close navigation"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-2 py-4">
        <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-gray-600">
          Navigation
        </p>
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className={cn(
                "group flex items-center gap-3 rounded-lg border px-3 py-2 text-sm font-medium transition-all duration-150",
                active
                  ? "border-blue-500/20 bg-blue-500/10 text-blue-400"
                  : "border-transparent text-gray-400 hover:bg-white/4 hover:text-gray-200",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors",
                  active ? "text-blue-400" : "text-gray-500 group-hover:text-gray-300",
                )}
              />
              {label}
              {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-blue-400" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="space-y-3 border-t border-white/5 px-4 py-4">
        <WorkerStatus />
        <a
          href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-xs text-gray-500 transition-colors hover:text-gray-300"
        >
          <Activity className="h-3.5 w-3.5" />
          API Docs
          <ExternalLink className="ml-auto h-3 w-3" />
        </a>
      </div>
    </aside>
  );
}

function WorkerStatus() {
  const [worker, setWorker] = useState<WorkerStatusResponse | null>(null);

  useEffect(() => {
    let active = true;

    async function poll() {
      try {
        const data = await getWorkerStatus();
        if (active) setWorker(data);
      } catch {
        if (active)
          setWorker({ status: "unknown", updated_at: null, last_heartbeat_ago_seconds: null });
      }
    }

    poll();
    const interval = setInterval(poll, 30_000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const alive   = worker?.status === "alive";
  const dead    = worker?.status === "dead";
  const loading = worker === null;

  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-white/5 bg-white/3 px-3 py-2">
      <div className="relative flex h-2 w-2 shrink-0">
        {alive && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
        )}
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            loading ? "bg-gray-600" : alive ? "bg-emerald-400" : "bg-red-400",
          )}
        />
      </div>
      <div>
        <p className="text-xs font-medium text-gray-300">Worker</p>
        <p
          className={cn(
            "text-[10px]",
            loading ? "text-gray-600" : alive ? "text-gray-600" : "text-red-500",
          )}
        >
          {loading ? "Checking…" : alive ? "Live" : dead ? "Offline" : "Unknown"}
        </p>
      </div>
    </div>
  );
}
