"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { opsApi } from "../../lib/api";
import type { AuthUserIdentity } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";

export default function DashboardPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const [user, setUser] = useState<AuthUserIdentity | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const loadUser = useCallback(async () => {
    if (!isAuthReady || !accessToken) {
      setUser(null);
      return;
    }
    setIsLoading(true);
    try {
      const result = await opsApi.getMe({ accessToken });
      setUser(result.user);
      setError("");
    } catch (requestError) {
      if (handleAuthError(requestError)) {
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "failed to load user");
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, handleAuthError, isAuthReady]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadUser();
  }, [isAuthReady, accessToken, loadUser]);

  if (!isAuthReady) {
    return (
      <main className="mx-auto grid w-[min(980px,92vw)] gap-4 py-7">
        <section className="panel p-5">
          <p className="text-sm text-muted">Checking authentication...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto grid w-[min(980px,92vw)] gap-4 py-7">
      <section className="panel p-5">
        <p className="text-xs uppercase tracking-[0.08em] text-muted">Dashboard</p>
        <h1 className="mt-1 font-display text-2xl">Welcome</h1>
        <p className="mt-2 text-sm text-muted">
          Signed in as <strong>{user?.email || "-"}</strong>
          {user?.display_name ? ` (${user.display_name})` : ""}.
        </p>
        <p className="mt-1 text-sm text-muted">Role: {user?.is_admin ? "admin" : "user"}</p>
        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}
      </section>

      <section className="panel p-5">
        <h2 className="font-display text-lg">User Views</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <NavButton href="/orders" label="Orders" />
          <NavButton href="/pnl" label="PnL Daily" />
          <NavButton href="/execution" label="Execution Metrics" />
          <NavButton href="/control" label="Bot Control" />
          {user?.is_admin ? <NavButton href="/admin/ops" label="Admin Ops Summary" /> : null}
        </div>
        <button
          className="mt-3 rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
          onClick={() => void loadUser()}
          disabled={isLoading}
        >
          {isLoading ? "Loading..." : "Refresh"}
        </button>
      </section>
    </main>
  );
}

function NavButton({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:border-black/20 hover:bg-black/5"
    >
      {label}
    </Link>
  );
}
