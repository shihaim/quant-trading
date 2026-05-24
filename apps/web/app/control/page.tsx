"use client";

import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../../lib/api";
import { asTime } from "../../lib/format";
import { useLocale } from "../../lib/locale";
import type { MeBotMutateResponse, MeBotStatusResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

type PendingAction = "start" | "stop" | null;

export default function ControlPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const { intlLocale, text } = useLocale();
  const [status, setStatus] = useState<MeBotStatusResponse | null>(null);
  const [lastMutation, setLastMutation] = useState<MeBotMutateResponse | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    if (!isAuthReady || !accessToken) {
      setStatus(null);
      return;
    }
    setIsLoading(true);
    try {
      const result = await opsApi.getMyBotStatus({ accessToken });
      setStatus(result);
      setError("");
      setLastLoadedAt(new Date().toISOString());
    } catch (requestError) {
      if (handleAuthError(requestError)) {
        return;
      }
      setError(text.controlLoadError);
      setStatus(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, handleAuthError, isAuthReady, text.controlLoadError]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadStatus();
  }, [isAuthReady, accessToken, loadStatus]);

  const applyAction = useCallback(async () => {
    if (!pendingAction || !isAuthReady || !accessToken) {
      return;
    }
    setIsMutating(true);
    try {
      const result =
        pendingAction === "start" ? await opsApi.startMyBot({ accessToken }) : await opsApi.stopMyBot({ accessToken });
      setLastMutation(result);
      setPendingAction(null);
      setError("");
      await loadStatus();
    } catch (requestError) {
      if (handleAuthError(requestError)) {
        return;
      }
      setError(text.controlUpdateError);
    } finally {
      setIsMutating(false);
    }
  }, [accessToken, handleAuthError, isAuthReady, loadStatus, pendingAction, text.controlUpdateError]);

  const actionLabel = pendingAction === "start" ? "START" : "STOP";

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
        <h1 className="mt-1 font-display text-3xl font-black tracking-tight">{text.control}</h1>
        <p className="mt-2 text-sm font-medium text-muted">{text.sourceControl}</p>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <article className="metric-card">
          <p className="text-xs text-muted">{text.automatedTradingStatus}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{status?.mode || "-"}</p>
        </article>
        <article className="metric-card">
          <p className="text-xs text-muted">{text.status}</p>
          <p className={`mt-1 font-display text-3xl font-black tracking-tight ${status?.is_enabled ? "text-safe" : "text-danger"}`}>
            {status?.status || "-"}
          </p>
        </article>
        <article className="metric-card">
          <p className="text-xs text-muted">{text.recentUpdate}</p>
          <p className="mt-1 font-display text-3xl font-black tracking-tight">{asTime(lastLoadedAt, intlLocale)}</p>
        </article>
      </section>

      <section className="data-panel">
        <h2 className="font-display text-xl font-black tracking-tight">{text.riskStatus}</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <SummaryCell label={text.riskStatus} value={status?.halt_reason ? text.attention : text.normal} detail={status?.halt_reason || text.riskSummary} />
          <SummaryCell label={text.orderLimitStatus} value={text.normal} detail={text.orderLimitSummary} />
          <SummaryCell
            label={text.cooldownStatus}
            value={status?.cooldown_until_kst || status?.cooldown_until_utc ? text.attention : text.noCooldown}
            detail={
              status?.cooldown_until_kst || status?.cooldown_until_utc
                ? `${text.cooldownUntil}: ${asTime(status.cooldown_until_kst || status.cooldown_until_utc, intlLocale)}`
                : text.cooldownSummary
            }
          />
        </div>
      </section>

      <section className="data-panel">
        <h2 className="font-display text-xl font-black tracking-tight">{text.controlActions}</h2>
        <p className="mt-1 text-sm text-muted">{text.controlFlowNote}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            className="btn btn-secondary"
            onClick={() => setPendingAction("start")}
            disabled={isLoading || isMutating || !status || status.is_enabled}
          >
            {text.requestStart}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => setPendingAction("stop")}
            disabled={isLoading || isMutating || !status || !status.is_enabled}
          >
            {text.requestStop}
          </button>
          <button className="btn btn-secondary" onClick={() => void loadStatus()} disabled={isLoading || isMutating}>
            {text.reloadStatus}
          </button>
        </div>
        {pendingAction ? (
          <div className="mt-4 rounded-2xl border border-amber-300 bg-amber-50 p-3">
            <p className="text-sm text-ink">
              {text.pendingAction}: <strong>{actionLabel}</strong>
            </p>
            <p className="mt-1 text-xs text-muted">{text.confirmAction}</p>
            <div className="mt-2 flex gap-2">
              <button className="btn btn-secondary" onClick={() => void applyAction()} disabled={isMutating}>
                {text.confirm} {actionLabel}
              </button>
              <button className="btn btn-secondary" onClick={() => setPendingAction(null)} disabled={isMutating}>
                {text.cancel}
              </button>
            </div>
          </div>
        ) : null}
        {lastMutation ? (
          <p className="mt-3 text-xs text-muted">
            {text.lastActionResult}: {lastMutation.is_enabled ? text.enabled : text.disabled} /{" "}
            {asTime(lastMutation.updated_at_kst || lastMutation.updated_at_utc, intlLocale)}
          </p>
        ) : null}
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>
    </main>
  );
}

function SummaryCell({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-line bg-[#f8fafc] p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 break-words font-display text-base font-black tracking-tight">{value}</p>
      <p className="mt-2 text-xs font-medium text-muted">{detail}</p>
    </div>
  );
}
