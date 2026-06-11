/**
 * Phase 8A frontend validation script.
 * Usage: node scripts/validate_phase8a.mjs
 */
import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const GREEN  = "\x1b[32m";
const RED    = "\x1b[31m";
const YELLOW = "\x1b[33m";
const RESET  = "\x1b[0m";

const results = [];

function record(name, status, detail = "") {
  results.push([name, status, detail]);
  const icon =
    status === "PASS" ? `${GREEN}[PASS]${RESET}` :
    status === "SKIP" ? `${YELLOW}[SKIP]${RESET}` :
                        `${RED}[FAIL]${RESET}`;
  console.log(`  ${icon}  ${name}${detail ? ` -- ${detail}` : ""}`);
}

function fileExists(rel) { return existsSync(join(ROOT, rel)); }

function readFile(rel) {
  const p = join(ROOT, rel);
  return existsSync(p) ? readFileSync(p, "utf8") : "";
}

function checkFile(name, rel) {
  record(name, fileExists(rel) ? "PASS" : "FAIL", fileExists(rel) ? "" : `missing: ${rel}`);
}

function checkContains(name, rel, pattern) {
  const text = readFile(rel);
  if (!text) { record(name, "FAIL", `${rel} not found`); return; }
  const rx = pattern instanceof RegExp ? pattern : new RegExp(pattern);
  record(name, rx.test(text) ? "PASS" : "FAIL", rx.test(text) ? "" : `pattern not found: ${pattern}`);
}

function checkNotContains(name, rel, pattern) {
  const text = readFile(rel);
  if (!text) { record(name, "FAIL", `${rel} not found`); return; }
  const rx = pattern instanceof RegExp ? pattern : new RegExp(pattern);
  record(name, !rx.test(text) ? "PASS" : "FAIL", !rx.test(text) ? "" : `unwanted pattern found: ${pattern}`);
}

// ── Dashboard routes ───────────────────────────────────────────────────────────
console.log("\n-- Dashboard pages exist --");
checkFile("(dashboard)/layout.tsx",                       "app/(dashboard)/layout.tsx");
checkFile("/dashboard page",                              "app/(dashboard)/dashboard/page.tsx");
checkFile("/reviews page",                                "app/(dashboard)/reviews/page.tsx");
checkFile("/reviews/[deliveryId] page",                   "app/(dashboard)/reviews/[deliveryId]/page.tsx");
checkFile("/repositories page",                           "app/(dashboard)/repositories/page.tsx");
checkFile("/repositories/[owner]/[repo] page",            "app/(dashboard)/repositories/[owner]/[repo]/page.tsx");

// ── API client ────────────────────────────────────────────────────────────────
console.log("\n-- API client (lib/api.ts) --");
checkFile("lib/api.ts exists", "lib/api.ts");
for (const fn of [
  "getAnalyticsOverview",
  "getReviews",
  "getReviewDetail",
  "getRepositories",
  "getRepositoryReviews",
  "getReviewsPerDay",
  "getSeverityDistribution",
  "getVerdictDistribution",
  "getRiskTrend",
]) {
  checkContains(`api.ts: ${fn}`, "lib/api.ts", fn);
}
checkContains("Uses NEXT_PUBLIC_API_URL",        "lib/api.ts", /NEXT_PUBLIC_API_URL/);
checkContains("Supports NEXT_PUBLIC_API_AUTH_TOKEN", "lib/api.ts", /NEXT_PUBLIC_API_AUTH_TOKEN/);
// localhost is allowed as the default fallback value alongside NEXT_PUBLIC_API_URL
const apiText = readFile("lib/api.ts");
const hasRawLocalhost = /['"`]http:\/\/localhost/.test(apiText);
const hasFallbackPattern = /NEXT_PUBLIC_API_URL.+localhost|localhost.+NEXT_PUBLIC_API_URL/s.test(apiText);
record(
  "No raw localhost without env var fallback",
  !hasRawLocalhost || hasFallbackPattern ? "PASS" : "FAIL",
  !hasRawLocalhost || hasFallbackPattern ? "" : "localhost found without NEXT_PUBLIC_API_URL fallback",
);

// ── Types ─────────────────────────────────────────────────────────────────────
console.log("\n-- Types (types/api.ts) --");
checkFile("types/api.ts exists", "types/api.ts");
for (const t of [
  "AnalyticsOverview",
  "ReviewListItem",
  "ReviewDetail",
  "RepositoryListItem",
  "PaginatedResponse",
  "Finding",
  "SubmissionInfo",
  "DailyReview",
  "SeverityDistribution",
  "VerdictDistribution",
]) {
  checkContains(`types/api.ts: ${t}`, "types/api.ts", t);
}

// ── Core UI components ────────────────────────────────────────────────────────
console.log("\n-- UI components --");
checkFile("MetricCard",         "components/ui/MetricCard.tsx");
checkFile("StatusBadge",        "components/ui/StatusBadge.tsx");
checkFile("SeverityBadge",      "components/ui/SeverityBadge.tsx");
checkFile("RiskBadge",          "components/ui/RiskBadge.tsx");
checkFile("EmptyState",         "components/ui/EmptyState.tsx");
checkFile("LoadingSkeleton",    "components/ui/LoadingSkeleton.tsx");

// ── Layout components ─────────────────────────────────────────────────────────
console.log("\n-- Layout components --");
checkFile("AppShell",  "components/layout/AppShell.tsx");
checkFile("Sidebar",   "components/layout/Sidebar.tsx");
checkFile("Topbar",    "components/layout/Topbar.tsx");

// ── Chart components ──────────────────────────────────────────────────────────
console.log("\n-- Chart components --");
checkFile("ReviewsPerDayChart",         "components/charts/ReviewsPerDayChart.tsx");
checkFile("SeverityDistributionChart",  "components/charts/SeverityDistributionChart.tsx");
checkFile("VerdictDistributionChart",   "components/charts/VerdictDistributionChart.tsx");
checkFile("RiskTrendChart",             "components/charts/RiskTrendChart.tsx");
for (const chart of [
  "components/charts/ReviewsPerDayChart.tsx",
  "components/charts/SeverityDistributionChart.tsx",
  "components/charts/VerdictDistributionChart.tsx",
  "components/charts/RiskTrendChart.tsx",
]) {
  checkContains(`${chart}: 'use client'`, chart, /['"]use client['"]/);
}

// ── Package deps ──────────────────────────────────────────────────────────────
console.log("\n-- package.json dependencies --");
const pkg = JSON.parse(readFile("package.json") || "{}");
const deps = { ...(pkg.dependencies ?? {}), ...(pkg.devDependencies ?? {}) };
for (const dep of ["recharts", "framer-motion", "date-fns", "lucide-react"]) {
  record(`dep: ${dep}`, dep in deps ? "PASS" : "FAIL", dep in deps ? "" : "not in package.json");
}

// ── No hardcoded localhost in pages ──────────────────────────────────────────
console.log("\n-- No raw localhost in page components --");
const pages = [
  "app/(dashboard)/dashboard/page.tsx",
  "app/(dashboard)/reviews/page.tsx",
  "app/(dashboard)/repositories/page.tsx",
];
for (const p of pages) {
  // Allow localhost references only when reading from process.env
  const text = readFile(p);
  const hasBad = /['"`]http:\/\/localhost/.test(text) && !/NEXT_PUBLIC_API_URL/.test(text);
  record(`${p}: no raw localhost`, hasBad ? "FAIL" : "PASS");
}

// ── Summary ───────────────────────────────────────────────────────────────────
console.log("\n" + "=".repeat(60));
const passed  = results.filter(([, s]) => s === "PASS").length;
const failed  = results.filter(([, s]) => s === "FAIL").length;
const skipped = results.filter(([, s]) => s === "SKIP").length;
console.log(`  Phase 8A frontend: ${passed} PASS  ${failed} FAIL  ${skipped} SKIP`);
console.log("=".repeat(60));

process.exit(failed > 0 ? 1 : 0);
