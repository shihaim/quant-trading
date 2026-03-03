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

## Commit Message Requests

- If the user asks for a commit message, read `.github/commit-message.instructions.md` first and follow it before drafting the message.
