# AGENTS.md

## Context Cost Rules

1. `node_modules`, `.next`, `logs`, `dist`, `build` are excluded from default search/explore scope.
2. Use `rg` with excludes by default.
   `rg -n "pattern" apps/web -g "!**/node_modules/**" -g "!**/.next/**" -g "!**/logs/**"`
3. List files with excludes.
   `rg --files apps/web -g "!**/node_modules/**" -g "!**/.next/**" -g "!**/logs/**"`
4. Start reads as partial reads (`-TotalCount`, `-First`, `-Tail`). Avoid full-file dumps by default.
5. For logs, read only recent lines.
   `Get-Content -Tail 100 <path>`
6. Summarize large command output; do not repeatedly paste full raw output.
7. Narrow edit scope to explicit target files before patching.
8. Exclude build artifacts (`.next`) and dependencies (`node_modules`) from commit/review scope.
9. Share only key error lines/stack excerpts instead of full build logs.
10. Default to summary-first; expand only when explicitly requested.

## Context Anchor Hook

- For tasks that touch trading behavior or invariants, choose the anchor first:
- Read `docs/context_anchor.md` first for current trading/runtime/Ops invariants.
- If the task needs historical V3 transition detail, compatibility removal context, or old backlog guardrails, also read `docs/context_anchor_v3_transition.md`.
- Trigger this hook when the task involves any of: scheduler flow, order execution, reconcile, fills, PnL, risk limits, runtime config, or Ops API behavior.
- Read the selected anchor with partial reads first (for example `-TotalCount`, `-First`, `-Tail`), then open only the relevant code files.
- Before patching, state which invariant(s) from the selected anchor must remain true.
- Skip this hook for purely presentational frontend changes in `apps/web` or docs-only wording updates with no behavior change.

## Commit Message Requests

- If the user asks for a commit message, read `.github/commit-message.instructions.md` first and follow it before drafting the message.

## Notion Ticket Protocol

- Canonical ticket index page: `https://www.notion.so/shihaim/Task-31b899b6d7dc80d4af4be0041af7937d?source=copy_link`
- This page is the source of truth for Story-Task-Sub-task ticket structure.
- Local `ticket/` directory has been removed; use Notion pages only for ticket planning and execution context.
- Default read scope: the canonical page and its direct child pages only.
- Current known child pages (as of 2026-03-08):
  - `[ARCHIVE] 2026-03-03 Frontend MVP Follow-up (Story-Task-Sub-task)`
  - `[ARCHIVE] 2026-03-04 V2 Foundation (Story-Task-Sub-task)`
  - `2026-03-06 V3 Multi-User Core Transition (Story-Task-Sub-task)`
- For ticket-driven implementation requests:
  1. Read the canonical page first, then relevant child page(s).
  2. Extract `Story`, `Tasks`, `Sub-tasks`, and `Acceptance` into a short execution checklist.
  3. Before patching, state which Story ID(s) are being implemented.
  4. After patching, map completed code changes back to Story/Task/Sub-task items.
- Archive handling:
  - Pages prefixed with `[ARCHIVE]` are reference tickets by default.
  - Do not treat archived tickets as active backlog unless the user explicitly asks.
- Notion write safety (when asked to update Notion):
  1. Propose write target page URL and draft content first.
  2. Apply writes only after explicit user confirmation in the same thread.
  3. After write, report changed page URL(s) and a concise change summary.
