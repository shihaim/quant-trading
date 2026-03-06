"use client";

import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../../lib/api";
import { asTime, short } from "../../lib/format";
import type { MeOrdersResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

const ORDER_STATES = ["ALL", "ERROR_NEEDS_REVIEW", "OPEN", "PARTIAL"] as const;
const LIMIT_OPTIONS = [25, 50, 100, 200] as const;

export default function OrdersPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const [stateFilter, setStateFilter] = useState<(typeof ORDER_STATES)[number]>("ALL");
  const [limit, setLimit] = useState<number>(50);
  const [payload, setPayload] = useState<MeOrdersResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    if (!isAuthReady || !accessToken) {
      setPayload(null);
      return;
    }
    setIsLoading(true);
    try {
      const result = await opsApi.getMyOrders({
        accessToken,
        state: stateFilter === "ALL" ? undefined : stateFilter,
        limit
      });
      setPayload(result);
      setError("");
      setLastLoadedAt(new Date().toISOString());
    } catch (requestError) {
      if (handleAuthError(requestError)) {
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "failed to load orders");
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, handleAuthError, isAuthReady, limit, stateFilter]);

  useEffect(() => {
    if (isAuthReady && accessToken) {
      void loadOrders();
    }
  }, [accessToken, isAuthReady, loadOrders]);

  const rows = payload?.items ?? [];

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
        <p className="text-xs uppercase tracking-[0.08em] text-muted">P1-FE3</p>
        <h1 className="mt-1 font-display text-2xl">Orders</h1>
        <p className="mt-2 text-sm text-muted">
          User-scoped order state view from <code>GET /api/me/orders</code>.
        </p>
      </header>

      <section className="panel p-4">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-muted">
            State
            <select
              className="ml-2 rounded-md border border-black/10 bg-white px-2 py-1 text-sm text-ink"
              value={stateFilter}
              onChange={(event) => setStateFilter(event.target.value as (typeof ORDER_STATES)[number])}
            >
              {ORDER_STATES.map((state) => (
                <option key={state} value={state}>
                  {state === "ALL" ? "ALL (recent)" : state}
                </option>
              ))}
            </select>
          </label>
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
            onClick={() => void loadOrders()}
            disabled={isLoading}
          >
            Reload
          </button>
          <p className="text-xs text-muted">Count: {payload?.count ?? 0}</p>
          <p className="text-xs text-muted">Loaded: {asTime(lastLoadedAt)}</p>
        </div>
        {payload?.scope ? (
          <p className="mt-2 text-xs text-muted">
            Scope: {payload.scope.mode} / user {payload.scope.user_id} / owner {payload.scope.owner_user_id}
          </p>
        ) : null}
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>

      <section className="panel overflow-auto p-2">
        <table className="min-w-[1180px] w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="border-b border-black/10 p-2">Updated</th>
              <th className="border-b border-black/10 p-2">Market</th>
              <th className="border-b border-black/10 p-2">Side</th>
              <th className="border-b border-black/10 p-2">Intent</th>
              <th className="border-b border-black/10 p-2">State</th>
              <th className="border-b border-black/10 p-2">Error Class</th>
              <th className="border-b border-black/10 p-2">Last Error</th>
              <th className="border-b border-black/10 p-2">Client Order ID</th>
              <th className="border-b border-black/10 p-2">Upbit Identifier</th>
              <th className="border-b border-black/10 p-2">Upbit UUID</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row) => (
                <tr key={row.id}>
                  <td className="border-b border-black/10 p-2">{asTime(row.updated_at_kst || row.updated_at_utc)}</td>
                  <td className="border-b border-black/10 p-2">{row.market}</td>
                  <td className="border-b border-black/10 p-2">{row.side || "-"}</td>
                  <td className="border-b border-black/10 p-2">{row.intent || "-"}</td>
                  <td className="border-b border-black/10 p-2">{row.state}</td>
                  <td className="border-b border-black/10 p-2" title={row.error_class || ""}>
                    {short(row.error_class, 36)}
                  </td>
                  <td className="border-b border-black/10 p-2" title={row.last_error || ""}>
                    {short(row.last_error, 64)}
                  </td>
                  <td className="border-b border-black/10 p-2" title={row.client_order_id}>
                    {short(row.client_order_id, 36)}
                  </td>
                  <td className="border-b border-black/10 p-2" title={row.upbit_identifier || ""}>
                    {short(row.upbit_identifier, 36)}
                  </td>
                  <td className="border-b border-black/10 p-2" title={row.upbit_uuid || ""}>
                    {short(row.upbit_uuid, 36)}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={10} className="border-b border-black/10 p-3 text-muted">
                  {isLoading ? "Loading..." : "No orders found for current filter."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}
