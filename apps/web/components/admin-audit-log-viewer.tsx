"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { opsApi } from "../lib/api";
import { sendClientLog, toErrorMessage } from "../lib/client-log";
import { asInt, asTime } from "../lib/format";
import type { AdminAuditLogsResponse } from "../lib/types";

type ResultFilter = "all" | "success" | "failure";

interface AuditFilters {
  actor_user_id: string;
  target_user_id: string;
  action: string;
  target_type: string;
  result: ResultFilter;
  from: string;
  to: string;
  limit: number;
}

const DEFAULT_LIMIT = 50;

function toIsoOrEmpty(value: string): string {
  if (!value.trim()) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return parsed.toISOString();
}

function toResultLabel(value: boolean | null): string {
  if (value === true) {
    return "success";
  }
  if (value === false) {
    return "failure";
  }
  return "-";
}

export function AdminAuditLogViewer({
  accessToken,
  onAuthError,
}: {
  accessToken: string;
  onAuthError?: (error: unknown) => boolean;
}) {
  const [payload, setPayload] = useState<AdminAuditLogsResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState<AuditFilters>(() => {
    const now = new Date();
    const from = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    return {
      actor_user_id: "",
      target_user_id: "",
      action: "",
      target_type: "",
      result: "all",
      from: from.toISOString().slice(0, 16),
      to: now.toISOString().slice(0, 16),
      limit: DEFAULT_LIMIT,
    };
  });

  const requestParams = useMemo(
    () => ({
      actor_user_id: filters.actor_user_id ? Number(filters.actor_user_id) : undefined,
      target_user_id: filters.target_user_id ? Number(filters.target_user_id) : undefined,
      action: filters.action.trim() || undefined,
      target_type: filters.target_type.trim() || undefined,
      result: filters.result,
      from: toIsoOrEmpty(filters.from) || undefined,
      to: toIsoOrEmpty(filters.to) || undefined,
      limit: filters.limit,
      offset,
    }),
    [filters, offset]
  );

  const loadLogs = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const response = await opsApi.getAdminAuditLogs({
        accessToken,
        ...requestParams,
      });
      setPayload(response);
      setError("");
    } catch (requestError) {
      if (onAuthError?.(requestError)) {
        return;
      }
      const message = toErrorMessage(requestError);
      setError(message);
      void sendClientLog({
        level: "ERROR",
        source: "admin-audit-log-viewer.loadLogs",
        message,
        context: {},
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, onAuthError, requestParams]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadLogs();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [loadLogs]);

  const canPrev = offset > 0;
  const canNext = Boolean(payload?.pagination.has_more);

  return (
    <section className="panel p-4">
      <div className="mb-3">
        <h2 className="font-display text-lg">Audit Logs</h2>
        <p className="text-xs text-muted">
          Admin-only read/search API. Default window is bounded to 7 days (max 31 days).
        </p>
      </div>

      <div className="mb-3 grid gap-2 md:grid-cols-4">
        <input
          className="rounded border border-black/10 bg-white px-2 py-1 text-sm"
          placeholder="actor_user_id"
          value={filters.actor_user_id}
          onChange={(event) => setFilters((prev) => ({ ...prev, actor_user_id: event.target.value }))}
        />
        <input
          className="rounded border border-black/10 bg-white px-2 py-1 text-sm"
          placeholder="target_user_id"
          value={filters.target_user_id}
          onChange={(event) => setFilters((prev) => ({ ...prev, target_user_id: event.target.value }))}
        />
        <input
          className="rounded border border-black/10 bg-white px-2 py-1 text-sm"
          placeholder="action"
          value={filters.action}
          onChange={(event) => setFilters((prev) => ({ ...prev, action: event.target.value }))}
        />
        <input
          className="rounded border border-black/10 bg-white px-2 py-1 text-sm"
          placeholder="target_type"
          value={filters.target_type}
          onChange={(event) => setFilters((prev) => ({ ...prev, target_type: event.target.value }))}
        />
      </div>

      <div className="mb-3 grid gap-2 md:grid-cols-4">
        <select
          className="rounded border border-black/10 bg-white px-2 py-1 text-sm"
          value={filters.result}
          onChange={(event) => setFilters((prev) => ({ ...prev, result: event.target.value as ResultFilter }))}
        >
          <option value="all">result: all</option>
          <option value="success">result: success</option>
          <option value="failure">result: failure</option>
        </select>
        <input
          className="rounded border border-black/10 bg-white px-2 py-1 text-sm"
          type="datetime-local"
          value={filters.from}
          onChange={(event) => setFilters((prev) => ({ ...prev, from: event.target.value }))}
        />
        <input
          className="rounded border border-black/10 bg-white px-2 py-1 text-sm"
          type="datetime-local"
          value={filters.to}
          onChange={(event) => setFilters((prev) => ({ ...prev, to: event.target.value }))}
        />
        <input
          className="rounded border border-black/10 bg-white px-2 py-1 text-sm"
          type="number"
          min={1}
          max={200}
          value={filters.limit}
          onChange={(event) =>
            setFilters((prev) => ({
              ...prev,
              limit: Math.max(1, Math.min(200, Number(event.target.value) || DEFAULT_LIMIT)),
            }))
          }
        />
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          className="rounded bg-black px-3 py-1 text-sm text-white"
          onClick={() => {
            setOffset(0);
            void loadLogs();
          }}
        >
          Apply Filters
        </button>
        <button
          className="rounded border border-black/20 px-3 py-1 text-sm"
          disabled={!canPrev}
          onClick={() => setOffset((prev) => Math.max(0, prev - filters.limit))}
        >
          Prev
        </button>
        <button
          className="rounded border border-black/20 px-3 py-1 text-sm"
          disabled={!canNext}
          onClick={() => setOffset((prev) => prev + filters.limit)}
        >
          Next
        </button>
        <p className="text-xs text-muted">
          offset {asInt(offset)} / returned {asInt(payload?.pagination.returned || 0)} / scanned{" "}
          {asInt(payload?.scan.scanned_rows || 0)}
        </p>
      </div>

      {error ? <p className="mb-3 text-sm text-red-700">{error}</p> : null}
      {isLoading && !payload ? <p className="mb-3 text-sm text-muted">Loading...</p> : null}

      <div className="overflow-x-auto rounded-lg border border-black/10 bg-white/70">
        <table className="min-w-[1200px] w-full border-collapse text-sm">
          <thead className="bg-black/5 text-left">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Actor</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Target</th>
              <th className="px-3 py-2">Result</th>
              <th className="px-3 py-2">Metadata</th>
            </tr>
          </thead>
          <tbody>
            {(payload?.items || []).map((item) => (
              <tr key={item.id} className="border-t border-black/10 align-top">
                <td className="px-3 py-2">
                  <p>{asTime(item.created_at_utc, "en-US")}</p>
                  <p className="text-xs text-muted">id={item.id}</p>
                </td>
                <td className="px-3 py-2">
                  <p>{item.actor_email || "-"}</p>
                  <p className="text-xs text-muted">user_id={item.actor_user_id || "-"}</p>
                </td>
                <td className="px-3 py-2">{item.action}</td>
                <td className="px-3 py-2">
                  <p>{item.target_type}</p>
                  <p className="text-xs text-muted">target_id={item.target_id || "-"}</p>
                  <p className="text-xs text-muted">target_user_id={item.target_user_id || "-"}</p>
                </td>
                <td className="px-3 py-2">{toResultLabel(item.is_success)}</td>
                <td className="px-3 py-2">
                  <details>
                    <summary className="cursor-pointer text-xs text-muted">expand</summary>
                    <pre className="mt-1 max-w-[560px] overflow-auto whitespace-pre-wrap rounded bg-black/5 p-2 text-xs">
                      {JSON.stringify(item.metadata, null, 2)}
                    </pre>
                  </details>
                </td>
              </tr>
            ))}
            {!payload?.items?.length && !isLoading ? (
              <tr>
                <td className="px-3 py-3 text-sm text-muted" colSpan={6}>
                  No audit rows in current filter range.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

