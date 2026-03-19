"use client";

import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../lib/api";
import { sendClientLog, toErrorMessage } from "../lib/client-log";
import { asInt, asPct, asTime, short } from "../lib/format";
import type { AdminRuntimeSummaryItem, AdminRuntimeSummaryResponse } from "../lib/types";

function toCredentialLabel(item: AdminRuntimeSummaryItem): string {
  if (!item.credential.has_credentials) {
    return "missing";
  }
  return item.credential.is_valid ? "valid" : "invalid";
}

function toRowTone(item: AdminRuntimeSummaryItem): string {
  if (item.flags.is_budget_blocked) {
    return "bg-red-50/70";
  }
  if (item.flags.is_halted) {
    return "bg-amber-50/70";
  }
  if (item.flags.is_credential_invalid) {
    return "bg-rose-50/60";
  }
  return "";
}

function toCriticalTags(item: AdminRuntimeSummaryItem): string[] {
  const tags: string[] = [];
  if (item.flags.is_budget_blocked) {
    tags.push("budget-blocked");
  }
  if (item.flags.is_halted) {
    tags.push("halted");
  }
  if (item.flags.is_credential_invalid) {
    tags.push("credential-invalid");
  }
  if (item.flags.has_runtime_error) {
    tags.push("runtime-error");
  }
  return tags;
}

export function AdminUsersRuntimeTable({
  accessToken,
  onAuthError,
}: {
  accessToken: string;
  onAuthError?: (error: unknown) => boolean;
}) {
  const [payload, setPayload] = useState<AdminRuntimeSummaryResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const loadSummary = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const response = await opsApi.getAdminUsersRuntimeSummary({ accessToken, limit: 300 });
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
        source: "admin-users-runtime-table.loadSummary",
        message,
        context: {},
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, onAuthError]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadSummary();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [loadSummary]);

  const items = payload?.items ?? [];

  return (
    <section className="panel p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-lg">User Runtime Summary</h2>
          <p className="text-xs text-muted">
            {isLoading ? "Loading..." : `${asInt(payload?.count || 0)} users`} / generated{" "}
            {asTime(payload?.generated_at_utc, "en-US")}
          </p>
        </div>
        <p className="text-xs text-muted">
          Sort: budget blocked - halted - credential invalid - recent action
        </p>
      </div>

      {error ? <p className="mb-3 text-sm text-red-700">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-black/10 bg-white/70">
        <table className="min-w-[1180px] w-full border-collapse text-sm">
          <thead className="bg-black/5 text-left">
            <tr>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Bot</th>
              <th className="px-3 py-2">Credential</th>
              <th className="px-3 py-2">Budget</th>
              <th className="px-3 py-2">Halt</th>
              <th className="px-3 py-2">Recent Activity</th>
              <th className="px-3 py-2">Flags</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const tags = toCriticalTags(item);
              return (
                <tr key={item.user_id} className={`border-t border-black/10 align-top ${toRowTone(item)}`}>
                  <td className="px-3 py-2">
                    <p className="font-medium">{item.display_name || item.email}</p>
                    <p className="text-xs text-muted">{item.email}</p>
                    <p className="text-xs text-muted">id={item.user_id}</p>
                  </td>
                  <td className="px-3 py-2">
                    <p>{item.role}</p>
                    <p className="text-xs text-muted">{item.is_active ? "active" : "inactive"}</p>
                  </td>
                  <td className="px-3 py-2">
                    <p>
                      {item.bot.status} / {item.bot.is_enabled ? "enabled" : "disabled"}
                    </p>
                    <p className="text-xs text-muted">runtime={item.bot.runtime_status}</p>
                    <p className="text-xs text-muted">last tick {asTime(item.bot.last_tick_utc, "en-US")}</p>
                  </td>
                  <td className="px-3 py-2">
                    <p>{toCredentialLabel(item)}</p>
                    <p className="text-xs text-muted">{item.credential.access_key_masked || "-"}</p>
                    <p className="text-xs text-muted">
                      key={item.credential.key_version || "-"} / {asTime(item.credential.updated_at_utc, "en-US")}
                    </p>
                  </td>
                  <td className="px-3 py-2">
                    <p>
                      req {asInt(item.budget.request_count)} / {asInt(item.budget.limit)}
                    </p>
                    <p className="text-xs text-muted">blocked {asInt(item.budget.blocked_count)}</p>
                    <p className="text-xs text-muted">remaining {asInt(item.budget.remaining)}</p>
                  </td>
                  <td className="px-3 py-2">
                    <p>{item.halt.reason || "-"}</p>
                    <p className="text-xs text-muted">{short(item.halt.message || "-", 64)}</p>
                    <p className="text-xs text-muted">
                      pnl {asPct(item.today_pnl.daily_pnl_pct, "en-US")} / threshold {asPct(item.today_pnl.halt_threshold_pct, "en-US")}
                    </p>
                  </td>
                  <td className="px-3 py-2">
                    <p className="text-xs">action {asTime(item.activity.recent_action_at_utc, "en-US")}</p>
                    <p className="text-xs text-muted">order {asTime(item.activity.recent_order_at_utc, "en-US")}</p>
                    <p className="text-xs text-muted">audit {asTime(item.activity.recent_audit_at_utc, "en-US")}</p>
                    <p className="text-xs text-muted">error {asTime(item.activity.recent_error_at_utc, "en-US")}</p>
                  </td>
                  <td className="px-3 py-2">
                    {tags.length ? (
                      <p className="text-xs font-medium text-red-700">{tags.join(", ")}</p>
                    ) : (
                      <p className="text-xs text-muted">normal</p>
                    )}
                    {item.runtime.last_error ? (
                      <p className="mt-1 text-xs text-red-800">{short(item.runtime.last_error, 72)}</p>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            {!items.length && !isLoading ? (
              <tr>
                <td className="px-3 py-3 text-sm text-muted" colSpan={8}>
                  No users found.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

