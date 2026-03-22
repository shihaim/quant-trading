"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { opsApi } from "../lib/api";
import { sendClientLog, toErrorMessage } from "../lib/client-log";
import { asDecimal, asInt, asKrw, asPct, asTime, short } from "../lib/format";
import { DASHBOARD_TEXT, type DashboardText, type LocaleCode } from "../lib/i18n";
import type { OpsSummary } from "../lib/types";

const POLLING_OPTIONS = [10000, 15000, 30000];
const LOCALE_STORAGE_KEY = "ops_locale";

function normalizeLossUsage(summary: OpsSummary | null): number {
  if (!summary) {
    return 0;
  }
  const threshold = Math.abs(summary.today_pnl.halt_threshold_pct || 0);
  const currentLoss = Math.max(0, -(summary.today_pnl.daily_pnl_pct || 0));
  if (threshold <= 0) {
    return 0;
  }
  return Math.min(100, (currentLoss / threshold) * 100);
}

function toStatusLabel(status: string, text: DashboardText): string {
  switch (status) {
    case "RUNNING":
      return text.statusRunning;
    case "HALTED":
      return text.statusHalted;
    case "DISABLED":
      return text.statusDisabled;
    case "DEGRADED":
      return text.statusDegraded;
    default:
      return status || "-";
  }
}

function toHaltReasonLabel(reason: string | null | undefined, text: DashboardText): string {
  switch (reason) {
    case "daily_loss_limit":
      return text.haltDailyLoss;
    case "weekly_loss_limit":
      return "WEEKLY_LOSS";
    case "monthly_loss_limit":
      return "MONTHLY_LOSS";
    case "new_orders_daily_limit":
      return "DAILY_ORDER_LIMIT";
    case "orders_weekly_limit":
      return "WEEKLY_ORDER_LIMIT";
    case "cooldown_active":
      return "COOLDOWN";
    case "auto_halt_by_slippage":
      return text.haltSlippage;
    default:
      return reason || "-";
  }
}

function toSideLabel(side: string | null | undefined, text: DashboardText): string {
  const normalized = String(side || "").toLowerCase();
  if (normalized === "bid") {
    return text.sideBid;
  }
  if (normalized === "ask") {
    return text.sideAsk;
  }
  return side || "-";
}

function toIntentLabel(intent: string | null | undefined, text: DashboardText): string {
  const normalized = String(intent || "").toUpperCase();
  if (normalized === "ENTRY") {
    return text.entry;
  }
  if (normalized === "EXIT") {
    return text.exit;
  }
  if (normalized === "REBALANCE") {
    return text.rebalance;
  }
  return intent || "-";
}

function toHaltThresholdLabel(summary: OpsSummary | null, text: DashboardText, locale: "en-US" | "ko-KR"): string {
  if (!summary) {
    return "-";
  }
  if (summary.halt.reason === "auto_halt_by_slippage") {
    return `${text.entry} ${asPct(summary.config.slippage_budget_entry_pct, locale)} / ${text.exit} ${asPct(
      summary.config.slippage_budget_exit_pct,
      locale
    )} / HALT ${asInt(summary.config.slippage_budget_breach_halt_count, locale)}`;
  }
  if (summary.halt.reason === "weekly_loss_limit") {
    return asPct(summary.config.max_weekly_loss_pct, locale);
  }
  if (summary.halt.reason === "monthly_loss_limit") {
    return asPct(summary.config.max_monthly_loss_pct, locale);
  }
  if (summary.halt.reason === "new_orders_daily_limit") {
    return `${asInt(summary.risk_policy.new_orders_today, locale)} / ${asInt(summary.config.max_new_orders_per_day, locale)}`;
  }
  if (summary.halt.reason === "orders_weekly_limit") {
    return `${asInt(summary.risk_policy.orders_this_week, locale)} / ${asInt(summary.config.max_orders_per_week, locale)}`;
  }
  const threshold = Math.abs(summary.today_pnl.halt_threshold_pct || 0);
  return threshold > 0 ? asPct(threshold, locale) : "-";
}

export function OpsDashboard({
  accessToken,
  onAuthError,
}: {
  accessToken: string;
  onAuthError?: (error: unknown) => boolean;
}) {
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [pollingMs, setPollingMs] = useState<number>(15000);
  const [locale, setLocale] = useState<LocaleCode>("en");

  useEffect(() => {
    const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (saved === "ko" || saved === "en") {
      setLocale(saved);
      return;
    }
    if (window.navigator.language.toLowerCase().startsWith("ko")) {
      setLocale("ko");
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    document.documentElement.lang = locale === "ko" ? "ko" : "en";
  }, [locale]);

  useEffect(() => {
    const onError = (event: ErrorEvent) => {
      void sendClientLog({
        level: "ERROR",
        source: "window.onerror",
        message: event.message || "window_error",
        context: {
          filename: event.filename || "",
          line: event.lineno,
          column: event.colno
        }
      });
    };
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      void sendClientLog({
        level: "ERROR",
        source: "window.unhandledrejection",
        message: toErrorMessage(event.reason),
        context: {}
      });
    };
    void sendClientLog({
      level: "INFO",
      source: "ops-dashboard",
      message: "page_loaded",
      context: {}
    });
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, []);

  const text = DASHBOARD_TEXT[locale];
  const intlLocale = locale === "ko" ? "ko-KR" : "en-US";

  const loadSummary = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const data = await opsApi.getSummary({ accessToken });
      setSummary(data);
      setError("");
    } catch (requestError) {
      if (onAuthError?.(requestError)) {
        return;
      }
      const errorMessage = toErrorMessage(requestError);
      setError(errorMessage);
      void sendClientLog({
        level: "ERROR",
        source: "ops-dashboard.loadSummary",
        message: errorMessage,
        context: {}
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
    }, pollingMs);
    return () => window.clearInterval(timer);
  }, [loadSummary, pollingMs]);

  const lossUsage = useMemo(() => normalizeLossUsage(summary), [summary]);

  const botStatusRaw = summary?.bot.status ?? "DISABLED";
  const botStatusLabel = toStatusLabel(botStatusRaw, text);
  const showAlert = Boolean(summary?.halt.is_halted || summary?.halt.reason);
  const haltThresholdLabel = toHaltThresholdLabel(summary, text, intlLocale);

  return (
    <main className="mx-auto grid w-[min(1200px,92vw)] gap-4 py-7">
      <header className="panel flex flex-col gap-4 p-4 md:flex-row md:items-start md:justify-between">
        <div className="grid gap-1">
          <p className="text-xs uppercase tracking-[0.08em] text-muted">{text.subtitle}</p>
          <h1 className="font-display text-2xl">{text.title}</h1>
          <p className="text-sm text-muted">
            {text.serverTime}: {asTime(summary?.server_time_kst || summary?.server_time_utc, intlLocale)}
            {error ? ` (error: ${error})` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-muted">
            {text.language}
            <div className="flex rounded-md border border-black/10 bg-white p-0.5">
              <button
                className={`rounded px-2 py-1 text-xs ${locale === "ko" ? "bg-black text-white" : ""}`}
                onClick={() => setLocale("ko")}
              >
                {text.korean}
              </button>
              <button
                className={`rounded px-2 py-1 text-xs ${locale === "en" ? "bg-black text-white" : ""}`}
                onClick={() => setLocale("en")}
              >
                {text.english}
              </button>
            </div>
          </label>
          <label className="flex items-center gap-2 text-sm text-muted">
            {text.polling}
            <select
              className="rounded-md border border-black/10 bg-white px-2 py-1 text-sm text-ink"
              value={pollingMs}
              onChange={(event) => setPollingMs(Number(event.target.value))}
            >
              {POLLING_OPTIONS.map((ms) => (
                <option key={ms} value={ms}>
                  {ms / 1000}s
                </option>
              ))}
            </select>
          </label>
          <button
            className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm"
            onClick={() => void loadSummary()}
            disabled={isLoading}
          >
            {text.refresh}
          </button>
        </div>
      </header>

      <section className="panel grid grid-cols-2 gap-2 p-3 md:grid-cols-4">
        <StatusChip label={text.mode} value={summary?.trade_mode || "-"} />
        <StatusChip label={text.bot} value={botStatusLabel} statusCode={botStatusRaw} />
        <StatusChip
          label={text.lastTick}
          value={asTime(summary?.bot.last_tick_kst || summary?.bot.last_tick_utc, intlLocale)}
        />
        <StatusChip label={text.haltReason} value={toHaltReasonLabel(summary?.halt.reason, text)} />
      </section>

      {showAlert ? (
        <section className="panel border-danger/40 bg-rose-50/70 p-4">
          <h2 className="font-display text-lg">{text.alertTitle}</h2>
          <p className="mt-1 text-sm text-muted">{summary?.halt.message || text.noHaltMessage}</p>
          <div className="mt-3 grid gap-2 md:grid-cols-3">
            <KpiCell
              label={text.triggered}
              value={asTime(summary?.halt.triggered_at_utc || summary?.bot.last_tick_utc, intlLocale)}
            />
            <KpiCell label={text.currentPnl} value={asPct(summary?.today_pnl.daily_pnl_pct, intlLocale)} />
            <KpiCell label={text.threshold} value={haltThresholdLabel} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <QuickLink href="/pnl">{text.viewPnl}</QuickLink>
            <QuickLink href="/control">{text.viewControl}</QuickLink>
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2">
        <article className="panel p-4">
          <h2 className="font-display text-lg">{text.todayPnl}</h2>
          <p className="mt-3 font-display text-4xl">{asPct(summary?.today_pnl.daily_pnl_pct, intlLocale)}</p>
          <p className="mt-1 text-sm text-muted">{asKrw(summary?.today_pnl.daily_pnl_abs, intlLocale)}</p>
          <p className="mt-2 text-sm text-muted">
            {text.basis}: {summary?.today_pnl.basis_used || "-"}
          </p>

          <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-black/10">
            <div
              className="h-full bg-gradient-to-r from-emerald-600 via-amber-500 to-red-500 transition-all"
              style={{ width: `${lossUsage.toFixed(1)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-muted">
            {text.lossUsage}: {lossUsage.toFixed(1)}% {text.ofDailyLimit}
          </p>

          <div className="mt-4 grid grid-cols-2 gap-2">
            <KpiCell label={text.start} value={asKrw(summary?.today_pnl.start_equity, intlLocale)} />
            <KpiCell label={text.last} value={asKrw(summary?.today_pnl.last_equity, intlLocale)} />
            <KpiCell label={text.realized} value={asKrw(summary?.today_pnl.realized_pnl, intlLocale)} />
            <KpiCell label={text.unrealized} value={asKrw(summary?.today_pnl.unrealized_pnl, intlLocale)} />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <QuickLink href="/pnl">{text.viewPnl}</QuickLink>
            <QuickLink href="/control">{text.viewControl}</QuickLink>
          </div>
        </article>

        <article className="panel p-4">
          <h2 className="font-display text-lg">{text.ordersRisk}</h2>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <KpiCell label="ERROR_NEEDS_REVIEW" value={asInt(summary?.orders.counts.ERROR_NEEDS_REVIEW, intlLocale)} />
            <KpiCell label="OPEN" value={asInt(summary?.orders.counts.OPEN, intlLocale)} />
            <KpiCell label="PARTIAL" value={asInt(summary?.orders.counts.PARTIAL, intlLocale)} />
            <KpiCell label="IN_FLIGHT" value={asInt(summary?.orders.counts.IN_FLIGHT, intlLocale)} />
          </div>

          <h3 className="mt-4 font-display text-base">{text.needsReviewTop}</h3>
          <div className="mt-2 overflow-auto">
            <table className="min-w-[580px] w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-muted">
                  <th className="border-b border-black/10 p-2">{text.updated}</th>
                  <th className="border-b border-black/10 p-2">{text.market}</th>
                  <th className="border-b border-black/10 p-2">{text.side}</th>
                  <th className="border-b border-black/10 p-2">{text.intent}</th>
                  <th className="border-b border-black/10 p-2">{text.error}</th>
                </tr>
              </thead>
              <tbody>
                {summary?.orders.needs_review_top.length ? (
                  summary.orders.needs_review_top.map((row) => (
                    <tr key={row.id}>
                      <td className="border-b border-black/10 p-2">{asTime(row.updated_at_utc, intlLocale)}</td>
                      <td className="border-b border-black/10 p-2">{row.market}</td>
                      <td className="border-b border-black/10 p-2">{toSideLabel(row.side, text)}</td>
                      <td className="border-b border-black/10 p-2">{toIntentLabel(row.intent, text)}</td>
                      <td className="border-b border-black/10 p-2" title={row.last_error || ""}>
                        {short(row.error_class || row.last_error)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="border-b border-black/10 p-2 text-muted">
                      {text.noRows}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <QuickLink href="/orders">{text.viewOrders}</QuickLink>
            <QuickLink href="/control">{text.viewControl}</QuickLink>
          </div>
        </article>
      </section>

      <section className="panel p-4">
        <h2 className="font-display text-lg">{text.executionQuality}</h2>
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-5">
          <KpiCell label={text.avgSlippage} value={asPct(summary?.execution_quality.kpi.avg_slippage_pct, intlLocale)} />
          <KpiCell label={text.p95Slippage} value={asPct(summary?.execution_quality.kpi.p95_slippage_pct, intlLocale)} />
          <KpiCell
            label={text.avgFillTime}
            value={`${asInt(summary?.execution_quality.kpi.avg_time_to_fill_ms, intlLocale)} ms`}
          />
          <KpiCell
            label={text.avgPartialFills}
            value={asDecimal(summary?.execution_quality.kpi.avg_partial_fill_count, intlLocale)}
          />
          <KpiCell label={text.breach24h} value={asInt(summary?.execution_quality.budget.breach_count_24h, intlLocale)} />
        </div>

        <div className="mt-3 overflow-auto">
          <table className="min-w-[560px] w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="border-b border-black/10 p-2">{text.executed}</th>
                <th className="border-b border-black/10 p-2">{text.market}</th>
                <th className="border-b border-black/10 p-2">{text.intent}</th>
                <th className="border-b border-black/10 p-2">{text.slipPct}</th>
                <th className="border-b border-black/10 p-2">{text.fillMs}</th>
              </tr>
            </thead>
            <tbody>
              {summary?.execution_quality.recent.length ? (
                summary.execution_quality.recent.slice(0, 20).map((row) => (
                  <tr key={`${row.order_id}-${row.executed_at_utc}`}>
                    <td className="border-b border-black/10 p-2">{asTime(row.executed_at_utc, intlLocale)}</td>
                    <td className="border-b border-black/10 p-2">{row.market || "-"}</td>
                    <td className="border-b border-black/10 p-2">{toIntentLabel(row.intent, text)}</td>
                    <td className="border-b border-black/10 p-2">{asPct(row.slippage_pct, intlLocale)}</td>
                    <td className="border-b border-black/10 p-2">{asInt(row.time_to_fill_ms, intlLocale)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="border-b border-black/10 p-2 text-muted">
                    {text.noRows}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <QuickLink href="/execution">{text.viewExecution}</QuickLink>
          <QuickLink href="/control">{text.viewControl}</QuickLink>
        </div>
      </section>

      <section className="panel p-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="font-display text-lg">{text.configSummary}</h2>
            <p className="text-sm text-muted">{text.updatedAt}: {asTime(summary?.config.updated_at_utc, intlLocale)}</p>
          </div>
          <QuickLink href="/control">{text.viewControl}</QuickLink>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          <KpiCell label={text.timeframe} value={summary?.config.timeframe || "-"} />
          <KpiCell label={text.markets} value={summary ? summary.config.markets.join(", ") : "-"} />
          <KpiCell
            label={text.dailyLossLimit}
            value={`${summary?.config.daily_loss_basis || "-"} / ${asPct(summary?.config.max_daily_loss_pct, intlLocale)}`}
          />
          <KpiCell label="Weekly loss limit" value={asPct(summary?.config.max_weekly_loss_pct, intlLocale)} />
          <KpiCell label="Monthly loss limit" value={asPct(summary?.config.max_monthly_loss_pct, intlLocale)} />
          <KpiCell label="Cooldown on halt" value={`${asInt(summary?.config.cooldown_hours_on_halt, intlLocale)}h`} />
          <KpiCell
            label="Order limits"
            value={`${asInt(summary?.risk_policy.new_orders_today, intlLocale)} / ${asInt(
              summary?.config.max_new_orders_per_day,
              intlLocale
            )} day, ${asInt(summary?.risk_policy.orders_this_week, intlLocale)} / ${asInt(
              summary?.config.max_orders_per_week,
              intlLocale
            )} week`}
          />
          <KpiCell label="Min edge" value={asPct(summary?.config.min_edge_pct, intlLocale)} />
          <KpiCell label={text.targetExposure} value={asPct(summary?.config.target_exposure_pct, intlLocale)} />
          <KpiCell label={text.maxTotalExposure} value={asPct(summary?.config.max_total_exposure_pct, intlLocale)} />
          <KpiCell label={text.maxPerMarket} value={asPct(summary?.config.max_per_market_exposure_pct, intlLocale)} />
          <KpiCell
            label={text.minRebalance}
            value={asPct(summary?.config.min_rebalance_threshold_pct, intlLocale)}
          />
          <KpiCell label={text.minOrderBuffer} value={asKrw(summary?.config.min_order_krw_buffer, intlLocale)} />
          <KpiCell
            label={text.fillTimeouts}
            value={`${text.entry} ${asInt(summary?.config.fill_timeout_sec_entry, intlLocale)}s / ${text.exit} ${asInt(
              summary?.config.fill_timeout_sec_exit,
              intlLocale
            )}s / ${text.rebalance} ${asInt(summary?.config.fill_timeout_sec_rebalance, intlLocale)}s`}
          />
          <KpiCell
            label={text.reprice}
            value={`${text.entry} ${asInt(summary?.config.max_reprice_attempts_entry, intlLocale)} / ${text.exit} ${asInt(
              summary?.config.max_reprice_attempts_exit,
              intlLocale
            )} / ${text.rebalance} ${asInt(summary?.config.max_reprice_attempts_rebalance, intlLocale)} @ ${asInt(
              summary?.config.reprice_step_bps,
              intlLocale
            )} bps`}
          />
          <KpiCell
            label={text.slippageBudget}
            value={`${text.entry} ${asPct(summary?.config.slippage_budget_entry_pct, intlLocale)} / ${text.exit} ${asPct(
              summary?.config.slippage_budget_exit_pct,
              intlLocale
            )} / HALT ${asInt(summary?.config.slippage_budget_breach_halt_count, intlLocale)}`}
          />
          <KpiCell
            label={text.notifyInterval}
            value={`${asInt(summary?.config.status_notify_interval_seconds, intlLocale)}s`}
          />
          <KpiCell label={text.updatedAt} value={asTime(summary?.config.updated_at_utc, intlLocale)} />
        </div>
      </section>
    </main>
  );
}

function QuickLink({ href, children }: { href: string; children: string }) {
  return (
    <Link
      href={href}
      className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:border-black/20 hover:bg-black/5"
    >
      {children}
    </Link>
  );
}

function StatusChip({
  label,
  value,
  statusCode
}: {
  label: string;
  value: string;
  statusCode?: string;
}) {
  const source = statusCode || value;
  const statusColor =
    source === "RUNNING"
      ? "text-safe"
      : source === "HALTED"
        ? "text-danger"
        : source === "DEGRADED"
          ? "text-amber-600"
          : "text-ink";
  return (
    <div className="rounded-xl border border-dashed border-black/10 p-3">
      <p className="text-[11px] uppercase tracking-[0.05em] text-muted">{label}</p>
      <p className={`font-display text-base ${statusColor}`}>{value}</p>
    </div>
  );
}

function KpiCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-black/10 p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 font-display text-base break-words">{value}</p>
    </div>
  );
}
