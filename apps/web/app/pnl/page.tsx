"use client";

import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../../lib/api";
import { asKrw, asPct, asTime } from "../../lib/format";
import { useLocale } from "../../lib/locale";
import type { MePnlDailyResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

const DAYS_OPTIONS = [7, 30, 60, 90] as const;

export default function PnlPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const { intlLocale, text } = useLocale();
  const [days, setDays] = useState<number>(30);
  const [payload, setPayload] = useState<MePnlDailyResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null);

  const loadPnl = useCallback(async () => {
    if (!isAuthReady || !accessToken) {
      setPayload(null);
      return;
    }
    setIsLoading(true);
    try {
      const result = await opsApi.getMyPnlDaily({
        accessToken,
        days,
        tz: "KST"
      });
      setPayload(result);
      setError("");
      setLastLoadedAt(new Date().toISOString());
    } catch (requestError) {
      if (handleAuthError(requestError)) {
        return;
      }
      setError(text.pnlLoadError);
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, days, handleAuthError, isAuthReady, text.pnlLoadError]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadPnl();
  }, [isAuthReady, accessToken, loadPnl]);

  const latest = payload?.items?.[0] ?? null;

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
        <h1 className="mt-1 font-display text-3xl font-black tracking-tight">{text.pnl}</h1>
        <p className="mt-2 text-sm font-medium text-muted">{text.sourcePnl}</p>
      </header>

      <section className="page-toolbar">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-muted">
            {text.days}
            <select
              className="ml-2 form-control inline-block w-auto py-1.5"
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
            >
              {DAYS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <button
            className="btn btn-secondary min-h-9"
            onClick={() => void loadPnl()}
            disabled={isLoading}
          >
            {text.refresh}
          </button>
          <p className="text-xs text-muted">{payload?.items.length ?? 0}{text.itemCount}</p>
          <p className="text-xs text-muted">{text.recentUpdate}: {asTime(lastLoadedAt, intlLocale)}</p>
        </div>
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <article className="metric-card">
          <p className="text-xs text-muted">{text.latestDailyPnl}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{asPct(latest?.daily_pnl_pct, intlLocale)}</p>
          <p className="text-sm text-muted">{asKrw(latest?.daily_pnl_abs, intlLocale)}</p>
        </article>
        <article className="metric-card">
          <p className="text-xs text-muted">{text.latestRealizedDaily}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{asPct(latest?.realized_daily_pct, intlLocale)}</p>
          <p className="text-sm text-muted">{asKrw(latest?.realized_daily_abs, intlLocale)}</p>
        </article>
        <article className="metric-card">
          <p className="text-xs text-muted">{text.latestEquity}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{asKrw(latest?.last_equity, intlLocale)}</p>
          <p className="text-sm text-muted">{text.date}: {latest?.date || "-"}</p>
        </article>
      </section>

      <section className="data-panel overflow-auto">
        <table className="min-w-[980px] w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="border-b border-black/10 p-2">{text.date}</th>
              <th className="border-b border-black/10 p-2">{text.startEquity}</th>
              <th className="border-b border-black/10 p-2">{text.lastEquity}</th>
              <th className="border-b border-black/10 p-2">{text.dailyPnl}</th>
              <th className="border-b border-black/10 p-2">{text.dailyPnlPct}</th>
              <th className="border-b border-black/10 p-2">{text.realizedDaily}</th>
              <th className="border-b border-black/10 p-2">{text.realizedDailyPct}</th>
              <th className="border-b border-black/10 p-2">{text.updated}</th>
            </tr>
          </thead>
          <tbody>
            {payload?.items.length ? (
              payload.items.map((row) => (
                <tr key={`${row.date}-${row.updated_at_utc || ""}`}>
                  <td className="border-b border-black/10 p-2">{row.date}</td>
                  <td className="border-b border-black/10 p-2">{asKrw(row.start_equity, intlLocale)}</td>
                  <td className="border-b border-black/10 p-2">{asKrw(row.last_equity, intlLocale)}</td>
                  <td className="border-b border-black/10 p-2">{asKrw(row.daily_pnl_abs, intlLocale)}</td>
                  <td className="border-b border-black/10 p-2">{asPct(row.daily_pnl_pct, intlLocale)}</td>
                  <td className="border-b border-black/10 p-2">{asKrw(row.realized_daily_abs, intlLocale)}</td>
                  <td className="border-b border-black/10 p-2">{asPct(row.realized_daily_pct, intlLocale)}</td>
                  <td className="border-b border-black/10 p-2">{asTime(row.updated_at_kst || row.updated_at_utc, intlLocale)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="border-b border-black/10 p-3 text-muted">
                  {isLoading ? text.reloading : text.latestDailyRowsEmpty}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}
