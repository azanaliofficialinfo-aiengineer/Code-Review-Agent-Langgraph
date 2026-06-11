/**
 * Phase 8A.5 frontend validation script.
 * Usage: node scripts/validate_phase8a5.mjs
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

const read  = (rel) => { const p = join(ROOT, rel); return existsSync(p) ? readFileSync(p, "utf8") : ""; };
const has   = (rel) => existsSync(join(ROOT, rel));
const chk   = (name, rel) => record(name, has(rel) ? "PASS" : "FAIL", has(rel) ? "" : `missing: ${rel}`);
const ok    = (name, rel, rx) => { const t = read(rel); if (!t) { record(name,"FAIL",`${rel} missing`); return; } record(name, rx.test(t) ? "PASS" : "FAIL", rx.test(t) ? "" : `pattern not found: ${rx}`); };
const notOk = (name, rel, rx) => { const t = read(rel); if (!t) { record(name,"FAIL",`${rel} missing`); return; } record(name, rx.test(t) ? "FAIL" : "PASS", rx.test(t) ? `unwanted pattern: ${rx}` : ""); };

// ── 1. WorkerStatus — real API call ──────────────────────────────────────────
console.log("\n-- 1. WorkerStatus: real API call --");
ok("getWorkerStatus exported from lib/api.ts",      "lib/api.ts",    /getWorkerStatus/);
ok("WorkerStatusResponse type exists",              "types/api.ts",  /WorkerStatusResponse/);
ok("Sidebar imports getWorkerStatus",               "components/layout/Sidebar.tsx", /getWorkerStatus/);
ok("Sidebar imports WorkerStatusResponse",          "components/layout/Sidebar.tsx", /WorkerStatusResponse/);
ok("WorkerStatus polls in useEffect",               "components/layout/Sidebar.tsx", /setInterval.*30[_,]000|30_000.*setInterval/s);
ok("WorkerStatus shows alive/dead/unknown states",  "components/layout/Sidebar.tsx", /Offline|dead/);
notOk("No hardcoded 'Live' only (must be dynamic)", "components/layout/Sidebar.tsx", /text-gray-600['">\s]+Live\s*<\/p>/);

// ── 2. Mobile sidebar ────────────────────────────────────────────────────────
console.log("\n-- 2. Mobile sidebar --");
ok("AppShell is client component",           "components/layout/AppShell.tsx",  /['"]use client['"]/);
ok("AppShell manages sidebarOpen state",     "components/layout/AppShell.tsx",  /sidebarOpen/);
ok("Mobile overlay in AppShell",             "components/layout/AppShell.tsx",  /backdrop-blur|lg:hidden/);
ok("Content offset is lg:pl-56 not pl-56",  "components/layout/AppShell.tsx",  /lg:pl-56/);
notOk("No bare pl-56 on content div",        "components/layout/AppShell.tsx",  /flex-col pl-56[^l]/);
ok("Sidebar accepts isOpen prop",            "components/layout/Sidebar.tsx",   /isOpen/);
ok("Sidebar accepts onClose prop",           "components/layout/Sidebar.tsx",   /onClose/);
ok("Sidebar translates for mobile",          "components/layout/Sidebar.tsx",   /-translate-x-full/);
ok("Close X button in sidebar",             "components/layout/Sidebar.tsx",   /Close navigation|lg:hidden/);
ok("Topbar has hamburger button",            "components/layout/Topbar.tsx",    /Open navigation|onMenuClick/);
ok("Hamburger hidden on desktop (lg:hidden)","components/layout/Topbar.tsx",   /lg:hidden/);

// ── 3. Accessibility ─────────────────────────────────────────────────────────
console.log("\n-- 3. Accessibility --");
// Clickable rows
for (const [label, file] of [
  ["dashboard",   "app/(dashboard)/dashboard/page.tsx"],
  ["reviews",     "app/(dashboard)/reviews/page.tsx"],
  ["repo-detail", "app/(dashboard)/repositories/[owner]/[repo]/page.tsx"],
]) {
  ok(`${label}: table rows have role="button"`,  file, /role=.button./);
  ok(`${label}: table rows have tabIndex={0}`,   file, /tabIndex=\{0\}/);
  ok(`${label}: table rows have onKeyDown`,       file, /onKeyDown/);
}
// Search label
ok("Reviews: search input has <label>",        "app/(dashboard)/reviews/page.tsx",        /htmlFor=.repo-filter.|sr-only/);
ok("Reviews: select has aria-label",           "app/(dashboard)/reviews/page.tsx",        /aria-label/);
// FindingCard
ok("FindingCard: role=button",                 "app/(dashboard)/reviews/[deliveryId]/page.tsx", /role=.button./);
ok("FindingCard: tabIndex={0}",                "app/(dashboard)/reviews/[deliveryId]/page.tsx", /tabIndex=\{0\}/);
ok("FindingCard: aria-expanded",               "app/(dashboard)/reviews/[deliveryId]/page.tsx", /aria-expanded/);
ok("FindingCard: onKeyDown",                   "app/(dashboard)/reviews/[deliveryId]/page.tsx", /onKeyDown/);

// ── 4. Pagination component ──────────────────────────────────────────────────
console.log("\n-- 4. Pagination component --");
chk("Pagination component file exists",  "components/ui/Pagination.tsx");
ok("Pagination has aria-label Prev",     "components/ui/Pagination.tsx", /aria-label=.Previous page./);
ok("Pagination has aria-label Next",     "components/ui/Pagination.tsx", /aria-label=.Next page./);
ok("Reviews page uses Pagination",       "app/(dashboard)/reviews/page.tsx",                        /Pagination/);
ok("Repositories page uses Pagination",  "app/(dashboard)/repositories/page.tsx",                   /Pagination/);
ok("Repo detail page uses Pagination",   "app/(dashboard)/repositories/[owner]/[repo]/page.tsx",    /Pagination/);

// ── 5. ChartCard component ───────────────────────────────────────────────────
console.log("\n-- 5. ChartCard component --");
chk("ChartCard component file exists", "components/ui/ChartCard.tsx");
ok("Dashboard imports ChartCard",      "app/(dashboard)/dashboard/page.tsx", /ChartCard/);

// ── 6. format.ts ─────────────────────────────────────────────────────────────
console.log("\n-- 6. lib/format.ts --");
chk("lib/format.ts exists",               "lib/format.ts");
ok("formatDuration exported",             "lib/format.ts",                              /export.*formatDuration/);
ok("Dashboard imports formatDuration",    "app/(dashboard)/dashboard/page.tsx",         /formatDuration/);
ok("Reviews imports formatDuration",      "app/(dashboard)/reviews/page.tsx",           /formatDuration/);
ok("Repo detail imports formatDuration",  "app/(dashboard)/repositories/[owner]/[repo]/page.tsx", /formatDuration/);

// ── 7. framer-motion removed ──────────────────────────────────────────────────
console.log("\n-- 7. framer-motion removed --");
const pkg = JSON.parse(read("package.json") || "{}");
const allDeps = { ...(pkg.dependencies ?? {}), ...(pkg.devDependencies ?? {}) };
record(
  "framer-motion not in package.json",
  "framer-motion" in allDeps ? "FAIL" : "PASS",
  "framer-motion" in allDeps ? "still listed — run npm install after removing" : "",
);
// Verify no stray imports either
const fmFiles = [
  "app/(dashboard)/dashboard/page.tsx",
  "components/layout/AppShell.tsx",
  "components/layout/Sidebar.tsx",
];
for (const f of fmFiles) {
  notOk(`${f}: no framer-motion import`, f, /from ['"]framer-motion['"]/);
}

// ── 8. Docker / env ───────────────────────────────────────────────────────────
console.log("\n-- 8. Docker + env --");
chk("frontend Dockerfile exists",             "Dockerfile");
ok("Dockerfile accepts NEXT_PUBLIC_API_URL ARG", "Dockerfile", /ARG NEXT_PUBLIC_API_URL/);
ok("frontend .env.example exists and documented", ".env.example", /NEXT_PUBLIC_API_URL/);
ok(".env.example explains build-time note",  ".env.example", /build time|BUILD TIME|build-time/i);

// ── 9. router.push (not window.location.href) ────────────────────────────────
console.log("\n-- 9. router.push instead of window.location.href --");
for (const [label, file] of [
  ["dashboard",   "app/(dashboard)/dashboard/page.tsx"],
  ["reviews",     "app/(dashboard)/reviews/page.tsx"],
  ["repo-detail", "app/(dashboard)/repositories/[owner]/[repo]/page.tsx"],
]) {
  notOk(`${label}: no window.location.href`, file, /window\.location\.href/);
  ok(`${label}: uses router.push`,           file, /router\.push/);
}

// ── Summary ───────────────────────────────────────────────────────────────────
console.log("\n" + "=".repeat(60));
const passed  = results.filter(([, s]) => s === "PASS").length;
const failed  = results.filter(([, s]) => s === "FAIL").length;
const skipped = results.filter(([, s]) => s === "SKIP").length;
console.log(`  Phase 8A.5 frontend: ${passed} PASS  ${failed} FAIL  ${skipped} SKIP`);
console.log("=".repeat(60));

process.exit(failed > 0 ? 1 : 0);
