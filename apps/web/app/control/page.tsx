"use client";

import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../../lib/api";
import { asPct, asTime } from "../../lib/format";
import type { MeBotMutateResponse, MeBotStatusResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

type PendingAction = "start" | "stop" | null;

export default function ControlPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
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
      setError(requestError instanceof Error ? requestError.message : "failed to load bot status");
      setStatus(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, handleAuthError, isAuthReady]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadStatus();
  }, [isAuthReady, accessToken, loadStatus]);

  const applyAction = useCallback(async () => {
    if (!pendingAction) {
      return;
    }
    if (!isAuthReady || !accessToken) {
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
      setError(requestError instanceof Error ? requestError.message : "failed to update bot status");
    } finally {
      setIsMutating(false);
    }
  }, [accessToken, handleAuthError, isAuthReady, loadStatus, pendingAction]);

  const actionLabel = pendingAction === "start" ? "START" : "STOP";

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
        <p className="text-xs uppercase tracking-[0.08em] text-muted">P1-FE6</p>
        <h1 className="mt-1 font-display text-2xl">Bot Control</h1>
        <p className="mt-2 text-sm text-muted">
          Dedicated control workflow for bot start/stop with guardrail context.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="panel p-4">
          <p className="text-xs text-muted">Mode</p>
          <p className="mt-1 font-display text-2xl">{status?.mode || "-"}</p>
        </article>
        <article className="panel p-4">
          <p className="text-xs text-muted">Status</p>
          <p className={`mt-1 font-display text-2xl ${status?.is_enabled ? "text-safe" : "text-danger"}`}>
            {status?.status || "-"}
          </p>
        </article>
        <article className="panel p-4">
          <p className="text-xs text-muted">Loaded</p>
          <p className="mt-1 font-display text-2xl">{asTime(lastLoadedAt)}</p>
        </article>
      </section>

      <section className="panel p-4">
        <h2 className="font-display text-lg">Guardrails (Read-only)</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          <GuardrailCell label="Daily loss basis" value={status?.daily_loss_basis || "-"} />
          <GuardrailCell label="Max daily loss" value={asPct(status?.max_daily_loss_pct)} />
          <GuardrailCell label="Target exposure" value={asPct(status?.target_exposure_pct)} />
          <GuardrailCell label="Max total exposure" value={asPct(status?.max_total_exposure_pct)} />
          <GuardrailCell label="Max per-market exposure" value={asPct(status?.max_per_market_exposure_pct)} />
          <GuardrailCell label="Updated at" value={asTime(status?.updated_at_kst || status?.updated_at_utc)} />
          <GuardrailCell label="Status source" value={status?.source || "-"} />
          <GuardrailCell label="Mutation source" value={lastMutation?.source || "-"} />
        </div>
      </section>

      <section className="panel p-4">
        <h2 className="font-display text-lg">Control Actions</h2>
        <p className="mt-1 text-sm text-muted">
          Two-step flow: first request action, then confirm. Actions are executed through authenticated{" "}
          <code>/api/me/bot/*</code> endpoints.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            className="rounded-md border border-safe/40 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
            onClick={() => setPendingAction("start")}
            disabled={isLoading || isMutating || !status || status.is_enabled}
          >
            Request Start
          </button>
          <button
            className="rounded-md border border-danger/50 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
            onClick={() => setPendingAction("stop")}
            disabled={isLoading || isMutating || !status || !status.is_enabled}
          >
            Request Stop
          </button>
          <button
            className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
            onClick={() => void loadStatus()}
            disabled={isLoading || isMutating}
          >
            Reload Status
          </button>
        </div>
        {pendingAction ? (
          <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3">
            <p className="text-sm text-ink">
              Pending action: <strong>{actionLabel}</strong>
            </p>
            <p className="mt-1 text-xs text-muted">Confirm to apply this action to the bot state.</p>
            <div className="mt-2 flex gap-2">
              <button
                className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
                onClick={() => void applyAction()}
                disabled={isMutating}
              >
                Confirm {actionLabel}
              </button>
              <button
                className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
                onClick={() => setPendingAction(null)}
                disabled={isMutating}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : null}
        {lastMutation ? (
          <p className="mt-3 text-xs text-muted">
            Last action result: {lastMutation.is_enabled ? "ENABLED" : "DISABLED"} at{" "}
            {asTime(lastMutation.updated_at_kst || lastMutation.updated_at_utc)}
          </p>
        ) : null}
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>
    </main>
  );
}

function GuardrailCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-black/10 p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 font-display text-base break-words">{value}</p>
    </div>
  );
}
