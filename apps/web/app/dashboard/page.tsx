"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../../lib/api";
import { asInt, asKrw, asPct, asTime } from "../../lib/format";
import { useLocale } from "../../lib/locale";
import type { AuthUserIdentity, MeOverviewResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

export default function DashboardPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const { intlLocale, text } = useLocale();
  const [user, setUser] = useState<AuthUserIdentity | null>(null);
  const [overview, setOverview] = useState<MeOverviewResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const loadDashboard = useCallback(async () => {
    if (!isAuthReady || !accessToken) {
      setUser(null);
      setOverview(null);
      return;
    }
    setIsLoading(true);
    try {
      const [identity, nextOverview] = await Promise.all([
        opsApi.getMe({ accessToken }),
        opsApi.getMyOverview({ accessToken }),
      ]);
      setUser(identity.user);
      setOverview(nextOverview);
      setError("");
    } catch (requestError) {
      if (handleAuthError(requestError)) {
        return;
      }
      setError(text.userLoadError);
      setUser(null);
      setOverview(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, handleAuthError, isAuthReady, text.userLoadError]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadDashboard();
  }, [isAuthReady, accessToken, loadDashboard]);

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
      <section className="page-header p-6 md:p-8">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{text.dashboard}</p>
            <h1 className="mt-2 font-display text-4xl font-black tracking-tight text-ink">{text.accountOverview}</h1>
            <p className="mt-3 text-sm font-medium text-muted">
              {text.overviewIntro}
            </p>
            <p className="mt-2 text-xs font-bold text-muted">
              {text.signedInAs} <strong className="text-ink">{user?.email || "-"}</strong>
              {user?.display_name ? ` (${user.display_name})` : ""}
            </p>
          </div>
          <div className="rounded-2xl border border-line bg-[#f8fafc] p-4">
            <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{text.recentUpdate}</p>
            <p className="mt-1 text-xl font-black tracking-tight text-ink">
              {asTime(overview?.last_updated_kst || overview?.last_updated_utc, intlLocale)}
            </p>
          </div>
        </div>
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <OverviewCard
          label={text.tradingHealth}
          value={overview?.bot.status || "-"}
          detail={overview?.bot.halt_reason || (overview?.bot.is_enabled ? text.enabled : text.disabled)}
          tone={overview?.bot.halt_reason ? "danger" : overview?.bot.is_enabled ? "safe" : "muted"}
        />
        <OverviewCard
          label={text.todayPnl}
          value={asPct(overview?.today_pnl.daily_pnl_pct, intlLocale)}
          detail={asKrw(overview?.today_pnl.daily_pnl_abs, intlLocale)}
          tone={(overview?.today_pnl.daily_pnl_abs ?? 0) < 0 ? "danger" : "safe"}
        />
        <OverviewCard
          label={text.upbitAuthStatus}
          value={credentialStatusValue(overview, text)}
          detail={credentialStatusDetail(overview, text)}
          tone={overview?.credential.status_level === "connected" ? "safe" : "danger"}
        />
        <OverviewCard
          label={text.reviewOrders}
          value={asInt(overview?.orders.needs_review_count, intlLocale)}
          detail={`${text.openOrders}: ${asInt(overview?.orders.open_count, intlLocale)}`}
          tone={(overview?.orders.needs_review_count ?? 0) > 0 ? "danger" : "muted"}
        />
      </section>

      <section className="data-panel p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">알림</p>
            <h2 className="mt-1 font-display text-xl font-black tracking-tight">지금 확인할 일</h2>
          </div>
          <span className="rounded-full bg-[#f1f5f9] px-3 py-1 text-xs font-black text-muted">
            {asInt(overview?.events?.length || 0, intlLocale)}건
          </span>
        </div>
        <div className="mt-4 grid gap-3">
          {(overview?.events ?? []).map((event) => (
            <article
              key={event.id}
              className={`rounded-xl border p-4 ${
                event.severity === "critical" ? "border-danger/30 bg-rose-50" : "border-amber-200 bg-amber-50/70"
              }`}
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-sm font-black text-ink">{event.title}</p>
                  <p className="mt-1 text-sm font-medium text-muted">{event.message}</p>
                  <p className="mt-2 text-xs font-bold text-muted">
                    {event.occurred_at_kst || event.occurred_at_utc ? asTime(event.occurred_at_kst || event.occurred_at_utc, intlLocale) : text.recentUpdate}
                  </p>
                </div>
                <Link className="btn btn-secondary min-h-9 px-3 text-xs" href={eventActionHref(event.action_view)}>
                  {event.action_label}
                </Link>
              </div>
            </article>
          ))}
          {overview && (overview.events || []).length === 0 ? (
            <div className="rounded-xl border border-line bg-white p-4 text-sm font-bold text-muted">
              지금 바로 조치할 알림이 없습니다.
            </div>
          ) : null}
        </div>
      </section>

      <section className="data-panel p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{text.workspace}</p>
            <h2 className="mt-1 font-display text-xl font-black tracking-tight">{text.secondaryActions}</h2>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => void loadDashboard()}
            disabled={isLoading}
          >
            {isLoading ? text.reloading : text.refresh}
          </button>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <NavButton href="/orders" label={text.orders} />
          <NavButton href="/pnl" label={text.pnl} />
          <NavButton href="/execution" label={text.execution} />
          <NavButton href="/credentials" label="업비트 인증" />
          <NavButton href="/control" label={text.control} />
          {user?.is_admin ? <NavButton href="/admin/ops" label={text.adminOps} /> : null}
        </div>
      </section>
    </main>
  );
}

function eventActionHref(actionView: string): string {
  switch (actionView) {
    case "credentials":
      return "/credentials";
    case "orders":
      return "/orders";
    case "control":
      return "/control";
    default:
      return "/dashboard";
  }
}

function credentialStatusValue(overview: MeOverviewResponse | null, text: ReturnType<typeof useLocale>["text"]): string {
  if (!overview) return "-";
  if (overview.credential.status_level === "connected") return text.connected;
  if (overview.credential.status_level === "needs_attention") return text.attention;
  return text.notConnected;
}

function credentialStatusDetail(overview: MeOverviewResponse | null, text: ReturnType<typeof useLocale>["text"]): string {
  if (!overview) return "-";
  if (overview.credential.status_level === "connected") return overview.credential.access_key_masked || "UPBIT";
  if (overview.credential.status_level === "needs_attention") return "새 키 저장 필요";
  return "업비트 키 등록 필요";
}

function NavButton({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="rounded-2xl border border-line bg-white px-4 py-4 text-sm font-black text-ink shadow-[0_12px_40px_rgba(0,0,0,0.01)] transition-colors hover:border-[#e2e8f0] hover:bg-[#f8fafc]"
    >
      {label}
    </Link>
  );
}

function OverviewCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "safe" | "danger" | "muted";
}) {
  const colorClass = tone === "safe" ? "text-safe" : tone === "danger" ? "text-danger" : "text-ink";
  return (
    <article className="metric-card">
      <p className="text-xs font-bold text-muted">{label}</p>
      <p className={`mt-2 break-words font-display text-3xl font-black tracking-tight ${colorClass}`}>{value}</p>
      <p className="mt-2 text-sm font-bold text-muted">{detail || "-"}</p>
    </article>
  );
}
