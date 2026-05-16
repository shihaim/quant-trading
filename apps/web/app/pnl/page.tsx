"use client";

import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../../lib/api";
import { asKrw, asPct, asTime } from "../../lib/format";
import type { MePnlDailyResponse, PnlTimezone } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

const DAYS_OPTIONS = [7, 30, 60, 90] as const;

export default function PnlPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const [days, setDays] = useState<number>(30);
  const [timezone, setTimezone] = useState<PnlTimezone>("UTC");
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
        tz: timezone
      });
      setPayload(result);
      setError("");
      setLastLoadedAt(new Date().toISOString());
    } catch (requestError) {
      if (handleAuthError(requestError)) {
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "failed to load pnl");
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, days, handleAuthError, isAuthReady, timezone]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadPnl();
  }, [isAuthReady, accessToken, loadPnl]);

  const latest = payload?.items?.[0] ?? null;

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
        <p className="text-xs uppercase tracking-[0.08em] text-muted">P1-FE4</p>
        <h1 className="mt-1 font-display text-2xl">PnL Daily</h1>
        <p className="mt-2 text-sm text-muted">
          User-scoped daily equity history from <code>GET /api/me/pnl/daily</code>.
        </p>
      </header>

      <section className="panel p-4">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-muted">
            Days
            <select
              className="ml-2 rounded-md border border-black/10 bg-white px-2 py-1 text-sm text-ink"
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
          <label className="text-sm text-muted">
            Timezone
            <select
              className="ml-2 rounded-md border border-black/10 bg-white px-2 py-1 text-sm text-ink"
              value={timezone}
              onChange={(event) => setTimezone(event.target.value as PnlTimezone)}
            >
              <option value="UTC">UTC</option>
              <option value="KST">KST</option>
            </select>
          </label>
          <button
            className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
            onClick={() => void loadPnl()}
            disabled={isLoading}
          >
            Reload
          </button>
          <p className="text-xs text-muted">Rows: {payload?.items.length ?? 0}</p>
          <p className="text-xs text-muted">Loaded: {asTime(lastLoadedAt)}</p>
        </div>
        {payload?.scope ? (
          <p className="mt-2 text-xs text-muted">
            Scope: {payload.scope.mode} / user {payload.scope.user_id} / compatibility user {payload.scope.owner_user_id}
          </p>
        ) : null}
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="panel p-4">
          <p className="text-xs text-muted">Latest Daily PnL</p>
          <p className="mt-1 font-display text-2xl">{asPct(latest?.daily_pnl_pct)}</p>
          <p className="text-sm text-muted">{asKrw(latest?.daily_pnl_abs)}</p>
        </article>
        <article className="panel p-4">
          <p className="text-xs text-muted">Latest Realized Daily</p>
          <p className="mt-1 font-display text-2xl">{asPct(latest?.realized_daily_pct)}</p>
          <p className="text-sm text-muted">{asKrw(latest?.realized_daily_abs)}</p>
        </article>
        <article className="panel p-4">
          <p className="text-xs text-muted">Latest Equity</p>
          <p className="mt-1 font-display text-2xl">{asKrw(latest?.last_equity)}</p>
          <p className="text-sm text-muted">Date: {latest?.date || "-"}</p>
        </article>
      </section>

      <section className="panel overflow-auto p-2">
        <table className="min-w-[980px] w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="border-b border-black/10 p-2">Date ({payload?.tz || timezone})</th>
              <th className="border-b border-black/10 p-2">Start Equity</th>
              <th className="border-b border-black/10 p-2">Last Equity</th>
              <th className="border-b border-black/10 p-2">Daily PnL</th>
              <th className="border-b border-black/10 p-2">Daily PnL %</th>
              <th className="border-b border-black/10 p-2">Realized Daily</th>
              <th className="border-b border-black/10 p-2">Realized Daily %</th>
              <th className="border-b border-black/10 p-2">Updated</th>
            </tr>
          </thead>
          <tbody>
            {payload?.items.length ? (
              payload.items.map((row) => (
                <tr key={`${row.date}-${row.updated_at_utc || ""}`}>
                  <td className="border-b border-black/10 p-2">{row.date}</td>
                  <td className="border-b border-black/10 p-2">{asKrw(row.start_equity)}</td>
                  <td className="border-b border-black/10 p-2">{asKrw(row.last_equity)}</td>
                  <td className="border-b border-black/10 p-2">{asKrw(row.daily_pnl_abs)}</td>
                  <td className="border-b border-black/10 p-2">{asPct(row.daily_pnl_pct)}</td>
                  <td className="border-b border-black/10 p-2">{asKrw(row.realized_daily_abs)}</td>
                  <td className="border-b border-black/10 p-2">{asPct(row.realized_daily_pct)}</td>
                  <td className="border-b border-black/10 p-2">{asTime(row.updated_at_kst || row.updated_at_utc)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="border-b border-black/10 p-3 text-muted">
                  {isLoading ? "Loading..." : "No daily rows found."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}
