"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { opsApi } from "../../lib/api";
import { asDecimal, asInt, asPct, asTime } from "../../lib/format";
import type { MeTradeMetricsResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

const LIMIT_OPTIONS = [50, 100, 200, 500] as const;

export default function ExecutionPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const [limit, setLimit] = useState<number>(200);
  const [payload, setPayload] = useState<MeTradeMetricsResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null);

  const loadMetrics = useCallback(async () => {
    if (!isAuthReady || !accessToken) {
      setPayload(null);
      return;
    }
    setIsLoading(true);
    try {
      const result = await opsApi.getMyTradeMetrics({ accessToken, limit });
      setPayload(result);
      setError("");
      setLastLoadedAt(new Date().toISOString());
    } catch (requestError) {
      if (handleAuthError(requestError)) {
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "failed to load metrics");
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, handleAuthError, isAuthReady, limit]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadMetrics();
  }, [isAuthReady, accessToken, loadMetrics]);

  const summary = useMemo(() => {
    const items = payload?.items ?? [];
    if (!items.length) {
      return {
        avgSlippagePct: null as number | null,
        avgFillMs: null as number | null,
        avgPartialFills: null as number | null
      };
    }
    const withSlippage = items.filter((item) => item.slippage_pct !== null);
    const withFillMs = items.filter((item) => item.time_to_fill_ms !== null);
    const avgSlippagePct = withSlippage.length
      ? withSlippage.reduce((acc, item) => acc + (item.slippage_pct ?? 0), 0) / withSlippage.length
      : null;
    const avgFillMs = withFillMs.length
      ? withFillMs.reduce((acc, item) => acc + (item.time_to_fill_ms ?? 0), 0) / withFillMs.length
      : null;
    const avgPartialFills = items.reduce((acc, item) => acc + (item.partial_fill_count || 0), 0) / items.length;
    return {
      avgSlippagePct,
      avgFillMs,
      avgPartialFills
    };
  }, [payload?.items]);

  if (!isAuthReady) {
    return (
      <main className="mx-auto grid w-[min(1200px,92vw)] gap-4 py-7">
        <section className="panel p-5">
          <p className="text-sm text-muted">Checking authentication...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto grid w-[min(1200px,92vw)] gap-4 py-7">
      <header className="panel p-4">
        <p className="text-xs uppercase tracking-[0.08em] text-muted">P1-FE5</p>
        <h1 className="mt-1 font-display text-2xl">Execution Metrics</h1>
        <p className="mt-2 text-sm text-muted">
          User-scoped execution metrics from <code>GET /api/me/metrics/trade</code>.
        </p>
      </header>

      <section className="panel p-4">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-muted">
            Limit
            <select
              className="ml-2 rounded-md border border-black/10 bg-white px-2 py-1 text-sm text-ink"
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
            >
              {LIMIT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <button
            className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
            onClick={() => void loadMetrics()}
            disabled={isLoading}
          >
            Reload
          </button>
          <p className="text-xs text-muted">Count: {payload?.count ?? 0}</p>
          <p className="text-xs text-muted">Loaded: {asTime(lastLoadedAt)}</p>
        </div>
        {payload?.scope ? (
          <p className="mt-2 text-xs text-muted">
            Scope: {payload.scope.mode} / user {payload.scope.user_id}
          </p>
        ) : null}
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <article className="panel p-4">
          <p className="text-xs text-muted">Rows</p>
          <p className="mt-1 font-display text-2xl">{asInt(payload?.count)}</p>
        </article>
        <article className="panel p-4">
          <p className="text-xs text-muted">Avg Slippage</p>
          <p className="mt-1 font-display text-2xl">{asPct(summary.avgSlippagePct)}</p>
        </article>
        <article className="panel p-4">
          <p className="text-xs text-muted">Avg Fill Time</p>
          <p className="mt-1 font-display text-2xl">{asInt(summary.avgFillMs)} ms</p>
        </article>
        <article className="panel p-4">
          <p className="text-xs text-muted">Avg Partial Fills</p>
          <p className="mt-1 font-display text-2xl">{asDecimal(summary.avgPartialFills)}</p>
        </article>
      </section>

      <section className="panel overflow-auto p-2">
        <table className="min-w-[1100px] w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="border-b border-black/10 p-2">Executed</th>
              <th className="border-b border-black/10 p-2">Market</th>
              <th className="border-b border-black/10 p-2">Side</th>
              <th className="border-b border-black/10 p-2">Intent</th>
              <th className="border-b border-black/10 p-2">Slippage %</th>
              <th className="border-b border-black/10 p-2">Fee (KRW)</th>
              <th className="border-b border-black/10 p-2">Time To Fill (ms)</th>
              <th className="border-b border-black/10 p-2">Partial Fills</th>
            </tr>
          </thead>
          <tbody>
            {payload?.items.length ? (
              payload.items.map((row) => (
                <tr key={`${row.order_id}-${row.created_at_utc || ""}-${row.intent || ""}`}>
                  <td className="border-b border-black/10 p-2">{asTime(row.created_at_kst || row.created_at_utc)}</td>
                  <td className="border-b border-black/10 p-2">{row.market || "-"}</td>
                  <td className="border-b border-black/10 p-2">{row.side || "-"}</td>
                  <td className="border-b border-black/10 p-2">{row.intent || "-"}</td>
                  <td className="border-b border-black/10 p-2">{asPct(row.slippage_pct)}</td>
                  <td className="border-b border-black/10 p-2">{asDecimal(row.fee_abs)}</td>
                  <td className="border-b border-black/10 p-2">{asInt(row.time_to_fill_ms)}</td>
                  <td className="border-b border-black/10 p-2">{asInt(row.partial_fill_count)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="border-b border-black/10 p-3 text-muted">
                  {isLoading ? "Loading..." : "No execution rows found."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}
