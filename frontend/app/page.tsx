import Link from "next/link";
import {
  GitPullRequestIcon,
  WorkflowIcon,
  BrainCircuitIcon,
  MessageSquareCodeIcon,
  GithubIcon,
  ZapIcon,
  DatabaseIcon,
  ArrowRight,
  BarChart3,
  ShieldCheck,
} from "lucide-react";

const features = [
  {
    icon: GithubIcon,
    title: "GitHub Webhooks",
    description: "Receives PR open and update events from GitHub App webhooks in real time via secure HMAC verification.",
    color: "from-violet-500/15 to-violet-500/5",
    border: "border-violet-500/20",
    iconColor: "text-violet-400",
    iconBg: "bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: WorkflowIcon,
    title: "LangGraph Workflow",
    description: "Multi-step agentic review pipeline orchestrated with LangGraph state machines — fetch, review, finalize.",
    color: "from-blue-500/15 to-blue-500/5",
    border: "border-blue-500/20",
    iconColor: "text-blue-400",
    iconBg: "bg-blue-500/10 border-blue-500/20",
  },
  {
    icon: BrainCircuitIcon,
    title: "Groq AI Review",
    description: "Pluggable AI backend — Groq with 120B parameter models delivers sub-second code intelligence.",
    color: "from-emerald-500/15 to-emerald-500/5",
    border: "border-emerald-500/20",
    iconColor: "text-emerald-400",
    iconBg: "bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: MessageSquareCodeIcon,
    title: "GitHub Review Payloads",
    description: "Posts structured inline review comments directly back to pull requests with severity-aware prioritization.",
    color: "from-amber-500/15 to-amber-500/5",
    border: "border-amber-500/20",
    iconColor: "text-amber-400",
    iconBg: "bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: DatabaseIcon,
    title: "PostgreSQL Analytics",
    description: "Every review, finding, and verdict persisted in PostgreSQL with composite indexes for dashboard queries.",
    color: "from-cyan-500/15 to-cyan-500/5",
    border: "border-cyan-500/20",
    iconColor: "text-cyan-400",
    iconBg: "bg-cyan-500/10 border-cyan-500/20",
  },
  {
    icon: BarChart3,
    title: "Live Dashboard",
    description: "Real-time analytics dashboard with severity trends, verdict distribution, and paginated review history.",
    color: "from-purple-500/15 to-purple-500/5",
    border: "border-purple-500/20",
    iconColor: "text-purple-400",
    iconBg: "bg-purple-500/10 border-purple-500/20",
  },
];

const pipeline = [
  { label: "GitHub",     color: "bg-gray-700 text-gray-300" },
  { label: "FastAPI",    color: "bg-blue-500/20 text-blue-300" },
  { label: "Redis",      color: "bg-red-500/20 text-red-300" },
  { label: "LangGraph",  color: "bg-violet-500/20 text-violet-300" },
  { label: "Groq AI",    color: "bg-emerald-500/20 text-emerald-300" },
  { label: "GH Review",  color: "bg-amber-500/20 text-amber-300" },
  { label: "Postgres",   color: "bg-cyan-500/20 text-cyan-300" },
  { label: "Dashboard",  color: "bg-purple-500/20 text-purple-300" },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#080810] text-white">
      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center overflow-hidden px-6 py-32 text-center">
        {/* Animated grid background */}
        <div className="absolute inset-0 grid-bg opacity-100" />
        {/* Radial gradient fade */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#080810]" />
        {/* Glow blobs */}
        <div className="absolute left-1/4 top-1/3 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-500/8 blur-3xl" />
        <div className="absolute right-1/4 top-1/2 h-48 w-48 translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-500/8 blur-3xl" />

        {/* Badge */}
        <div className="relative mb-8 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/8 px-4 py-1.5 text-xs font-medium text-blue-300">
          <ZapIcon className="h-3 w-3" />
          Production-grade DevTool · Phase 8A
        </div>

        {/* Title */}
        <h1 className="relative mb-5 max-w-3xl text-5xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl">
          Autonomous AI{" "}
          <span className="bg-gradient-to-r from-blue-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
            Pull Request Reviews
          </span>
        </h1>

        {/* Subtitle */}
        <p className="relative mb-10 max-w-2xl text-lg leading-relaxed text-gray-400">
          A production-grade DevTool that listens to GitHub PR webhooks, runs LangGraph review
          workflows, analyzes diffs with Groq AI, posts GitHub review payloads, and stores
          analytics in PostgreSQL.
        </p>

        {/* CTAs */}
        <div className="relative flex flex-wrap justify-center gap-4">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:shadow-blue-500/30 hover:-translate-y-0.5"
          >
            <BarChart3 className="h-4 w-4" />
            Open Dashboard
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/reviews"
            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-gray-300 backdrop-blur transition-all hover:bg-white/8 hover:text-white hover:-translate-y-0.5"
          >
            <GitPullRequestIcon className="h-4 w-4" />
            View Reviews
          </Link>
        </div>
      </section>

      {/* Pipeline visual */}
      <section className="relative px-6 pb-16">
        <div className="mx-auto max-w-4xl">
          <p className="mb-6 text-center text-xs font-semibold uppercase tracking-widest text-gray-600">
            Review Pipeline
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {pipeline.map((step, i) => (
              <div key={step.label} className="flex items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium ${step.color}`}
                >
                  {step.label}
                </span>
                {i < pipeline.length - 1 && (
                  <ArrowRight className="h-3 w-3 text-gray-700" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature cards */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <h2 className="mb-8 text-center text-sm font-semibold uppercase tracking-widest text-gray-600">
          Core Capabilities
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className={`group relative overflow-hidden rounded-xl border ${f.border} bg-gradient-to-b ${f.color} p-5 transition-all duration-200 hover:scale-[1.01] hover:shadow-lg hover:shadow-black/30`}
              >
                <div className={`mb-3 inline-flex rounded-lg border ${f.iconBg} p-2`}>
                  <Icon className={`h-4 w-4 ${f.iconColor}`} />
                </div>
                <h3 className="mb-1.5 font-semibold text-white">{f.title}</h3>
                <p className="text-sm leading-relaxed text-gray-400">{f.description}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 px-6 py-8">
        <div className="mx-auto flex max-w-6xl items-center justify-between text-xs text-gray-600">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded bg-gradient-to-br from-blue-500 to-violet-600">
              <ZapIcon className="h-3 w-3 text-white" />
            </div>
            <span>CodeReview Agent</span>
          </div>
          <div className="flex items-center gap-4">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
            <span>LangGraph · Groq · FastAPI · PostgreSQL · Next.js</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
