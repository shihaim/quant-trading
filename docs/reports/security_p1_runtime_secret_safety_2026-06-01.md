# Security P1 Runtime Secret Safety

Date: 2026-06-01

## Scope

Security P1 adds Ops API startup validation for production-like runtime settings.

Production-like runtime means:

- `TRADE_MODE=REAL`, `TEST`, or `SHADOW`
- or `OPS_API_ENV=production`

## Behavior

Ops API startup fails before database initialization or HTTP serving when production-like runtime uses:

- missing/default `OPS_API_AUTH_SECRET`
- missing/default `OPS_API_CREDENTIALS_ENCRYPTION_KEY`
- `OPS_API_ALLOW_ORIGIN=*`

`PAPER` local/preview runtime remains compatible with existing development defaults.

## Operator Notes

- Use a restricted production origin instead of wildcard CORS.
- Do not rotate `OPS_API_CREDENTIALS_ENCRYPTION_KEY`, active key version, or keyring without a credential rotation plan.
- Runtime secrets must stay in deployment environment configuration, not in source code or container images.
