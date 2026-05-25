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
          value={overview?.credential.has_credentials && overview.credential.is_valid ? text.connected : text.attention}
          detail={overview?.credential.has_credentials ? overview.credential.exchange : text.notConnected}
          tone={overview?.credential.has_credentials && overview.credential.is_valid ? "safe" : "danger"}
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
          <NavButton href="/control" label={text.control} />
          {user?.is_admin ? <NavButton href="/admin/ops" label={text.adminOps} /> : null}
        </div>
      </section>
    </main>
  );
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
