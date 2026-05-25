"use client";

import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../../lib/api";
import { asTime, short } from "../../lib/format";
import { useLocale } from "../../lib/locale";
import type { MeOrdersResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

const ORDER_STATES = ["ALL", "ERROR_NEEDS_REVIEW", "OPEN", "PARTIAL"] as const;
const LIMIT_OPTIONS = [25, 50, 100, 200] as const;

type OrderStateLabels = {
  [state: string]: string;
};

function orderStateLabel(state: string, labels: OrderStateLabels) {
  return labels[state] ?? state.replaceAll("_", " ");
}

function orderStateBadgeClass(state: string) {
  if (state === "ERROR_NEEDS_REVIEW" || state === "ERROR" || state === "REJECTED") {
    return "status-badge-red";
  }
  if (state === "PARTIAL" || state === "WAIT" || state === "SENT" || state === "NEW") {
    return "status-badge-amber";
  }
  if (state === "FILLED" || state === "TEST_OK") {
    return "status-badge-green";
  }
  if (state === "OPEN") {
    return "status-badge-blue";
  }
  return "status-badge-gray";
}

export default function OrdersPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const { intlLocale, text } = useLocale();
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
      setError(text.ordersLoadError);
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, handleAuthError, isAuthReady, limit, stateFilter, text.ordersLoadError]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadOrders();
  }, [isAuthReady, accessToken, loadOrders]);

  const rows = payload?.items ?? [];

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
        <h1 className="mt-1 font-display text-3xl font-black tracking-tight">{text.orders}</h1>
        <p className="mt-2 text-sm font-medium text-muted">{text.sourceOrders}</p>
      </header>

      <section className="page-toolbar">
        <div className="toolbar-row">
          <div className="toolbar-filters">
            <label className="text-sm text-muted">
              {text.state}
              <select
                className="ml-2 form-control inline-block w-auto py-1.5"
                value={stateFilter}
                onChange={(event) => setStateFilter(event.target.value as (typeof ORDER_STATES)[number])}
              >
                {ORDER_STATES.map((state) => (
                  <option key={state} value={state}>
                    {state === "ALL" ? text.allRecent : orderStateLabel(state, text.orderStateLabels)}
                  </option>
                ))}
              </select>
            </label>
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
              onClick={() => void loadOrders()}
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

      <section className="data-panel overflow-auto">
        <table className="data-table data-table-orders text-sm">
          <colgroup>
            <col className="w-[180px]" />
            <col className="w-[130px]" />
            <col className="w-[90px]" />
            <col className="w-[150px]" />
            <col className="w-[170px]" />
            <col className="w-[460px]" />
          </colgroup>
          <thead>
            <tr className="text-left text-muted">
              <th className="border-b border-black/10 p-2">{text.updated}</th>
              <th className="border-b border-black/10 p-2">{text.market}</th>
              <th className="border-b border-black/10 p-2">{text.side}</th>
              <th className="border-b border-black/10 p-2">{text.intent}</th>
              <th className="border-b border-black/10 p-2">{text.state}</th>
              <th className="border-b border-black/10 p-2">{text.orderNote}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row) => (
                <tr key={row.id}>
                  <td className="border-b border-black/10 p-2">{asTime(row.updated_at_kst || row.updated_at_utc, intlLocale)}</td>
                  <td className="border-b border-black/10 p-2">{row.market}</td>
                  <td className="border-b border-black/10 p-2">{row.side || "-"}</td>
                  <td className="border-b border-black/10 p-2">{row.intent || "-"}</td>
                  <td className="border-b border-black/10 p-2">
                    <span
                      className={`status-badge min-w-[116px] justify-center ${orderStateBadgeClass(row.state)}`}
                      title={row.state}
                    >
                      {orderStateLabel(row.state, text.orderStateLabels)}
                    </span>
                  </td>
                  <td className="border-b border-black/10 p-2" title={row.last_error || row.error_class || ""}>
                    <span className="table-truncate">{short(row.last_error || row.error_class, 96)}</span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="border-b border-black/10 p-3 text-muted">
                  {isLoading ? text.reloading : text.noOrders}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}
