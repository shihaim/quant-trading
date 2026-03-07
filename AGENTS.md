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
- If the task is about V3 transition, multi-user scoping, owner-bridge removal, or runtime ownership migration, read `docs/context_anchor_v3_transition.md` first.
- Otherwise, read `docs/context_anchor.md` first.
- Trigger this hook when the task involves any of: scheduler flow, order execution, reconcile, fills, PnL, risk limits, runtime config, or Ops API behavior.
- Read the selected anchor with partial reads first (for example `-TotalCount`, `-First`, `-Tail`), then open only the relevant code files.
- Before patching, state which invariant(s) from the selected anchor must remain true.
- Skip this hook for purely presentational frontend changes in `apps/web` or docs-only wording updates with no behavior change.

## Commit Message Requests

- If the user asks for a commit message, read `.github/commit-message.instructions.md` first and follow it before drafting the message.
