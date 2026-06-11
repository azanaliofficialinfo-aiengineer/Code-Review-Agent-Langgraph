"use client";

import { useState } from "react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

/**
 * AppShell manages the mobile sidebar open/close state.
 * It is a Client Component so it can hold useState; page children are still
 * server-rendered because they are passed in as the `children` prop slot.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#080810]">
      {/* Subtle grid texture behind everything */}
      <div className="pointer-events-none fixed inset-0 grid-bg opacity-100" />

      {/* Mobile overlay — tapping it closes the drawer */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content — offset only on large screens where sidebar is always visible */}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-56">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 px-4 py-5 lg:px-6 lg:py-6">{children}</main>
      </div>
    </div>
  );
}
