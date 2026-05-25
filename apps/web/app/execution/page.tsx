"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { opsApi } from "../../lib/api";
import { asDecimal, asInt, asPct, asTime } from "../../lib/format";
import { useLocale } from "../../lib/locale";
import type { MeTradeMetricsResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

const LIMIT_OPTIONS = [50, 100, 200, 500] as const;

export default function ExecutionPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const { intlLocale, text } = useLocale();
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
      setError(text.executionLoadError);
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, handleAuthError, isAuthReady, limit, text.executionLoadError]);

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
      <main className="page">
        <section className="panel p-5">
          <p className="text-sm text-muted">{text.checkingAuth}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="page-header">
        <h1 className="mt-1 font-display text-3xl font-black tracking-tight">{text.executionMetrics}</h1>
        <p className="mt-2 text-sm font-medium text-muted">{text.sourceExecution}</p>
      </header>

      <section className="page-toolbar">
        <div className="toolbar-row">
          <div className="toolbar-filters">
            <label className="text-sm text-muted">
              {text.limit}
              <select
                className="ml-2 form-control inline-block w-auto py-1.5"
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
          </div>
          <div className="toolbar-actions">
            <button
              className="btn btn-secondary min-h-9"
              onClick={() => void loadMetrics()}
              disabled={isLoading}
            >
              {text.refresh}
            </button>
            <div className="toolbar-meta">
              <p className="text-xs text-muted">{payload?.count ?? 0}{text.itemCount}</p>
              <p className="text-xs text-muted">{text.recentUpdate}: {asTime(lastLoadedAt, intlLocale)}</p>
            </div>
          </div>
        </div>
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="metric-card">
          <p className="text-xs text-muted">{text.tradeCount}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{asInt(payload?.count, intlLocale)}</p>
        </article>
        <article className="metric-card">
          <p className="text-xs text-muted">{text.avgSlippage}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{asPct(summary.avgSlippagePct, intlLocale)}</p>
        </article>
        <article className="metric-card">
          <p className="text-xs text-muted">{text.avgFillTime}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{asInt(summary.avgFillMs, intlLocale)} ms</p>
        </article>
        <article className="metric-card">
          <p className="text-xs text-muted">{text.avgPartialFills}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{asDecimal(summary.avgPartialFills, intlLocale)}</p>
        </article>
      </section>

      <section className="data-panel overflow-auto">
        <table className="data-table data-table-execution text-sm">
          <colgroup>
            <col className="w-[180px]" />
            <col className="w-[130px]" />
            <col className="w-[90px]" />
            <col className="w-[150px]" />
            <col className="w-[130px]" />
            <col className="w-[140px]" />
            <col className="w-[150px]" />
            <col className="w-[130px]" />
          </colgroup>
          <thead>
            <tr className="text-left text-muted">
              <th className="border-b border-black/10 p-2">{text.executed}</th>
              <th className="border-b border-black/10 p-2">{text.market}</th>
              <th className="border-b border-black/10 p-2">{text.side}</th>
              <th className="border-b border-black/10 p-2">{text.intent}</th>
              <th className="border-b border-black/10 p-2">{text.slippagePct}</th>
              <th className="border-b border-black/10 p-2">{text.feeKrw}</th>
              <th className="border-b border-black/10 p-2">{text.avgFillTime} (ms)</th>
              <th className="border-b border-black/10 p-2">{text.partialFills}</th>
            </tr>
          </thead>
          <tbody>
            {payload?.items.length ? (
              payload.items.map((row) => (
                <tr key={`${row.order_id}-${row.created_at_utc || ""}-${row.intent || ""}`}>
                  <td className="border-b border-black/10 p-2">{asTime(row.created_at_kst || row.created_at_utc, intlLocale)}</td>
                  <td className="border-b border-black/10 p-2">{row.market || "-"}</td>
                  <td className="border-b border-black/10 p-2">{row.side || "-"}</td>
                  <td className="border-b border-black/10 p-2">{row.intent || "-"}</td>
                  <td className="table-cell-number border-b border-black/10 p-2">{asPct(row.slippage_pct, intlLocale)}</td>
                  <td className="table-cell-number border-b border-black/10 p-2">{asDecimal(row.fee_abs, intlLocale)}</td>
                  <td className="table-cell-number border-b border-black/10 p-2">{asInt(row.time_to_fill_ms, intlLocale)}</td>
                  <td className="table-cell-number border-b border-black/10 p-2">{asInt(row.partial_fill_count, intlLocale)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="border-b border-black/10 p-3 text-muted">
                  {isLoading ? text.reloading : text.noExecutionRows}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}
