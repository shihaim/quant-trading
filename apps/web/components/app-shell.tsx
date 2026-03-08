"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { opsApi } from "../lib/api";
import { clearAuthSession, readAccessTokenOrEmpty } from "../lib/auth";

const PUBLIC_NAV_ITEMS = [{ href: "/", label: "Entry" }];

const AUTH_NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/orders", label: "Orders" },
  { href: "/pnl", label: "PnL" },
  { href: "/execution", label: "Execution Metrics" },
  { href: "/control", label: "Bot Control" }
];

const ADMIN_NAV_ITEMS = [{ href: "/admin/ops", label: "Admin Ops" }];

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [hasToken, setHasToken] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    let disposed = false;
    const token = readAccessTokenOrEmpty().trim();
    setHasToken(Boolean(token));
    setIsAdmin(false);
    if (!token) {
      return () => {
        disposed = true;
      };
    }
    void opsApi
      .getMe({ accessToken: token })
      .then((payload) => {
        if (!disposed) {
          setIsAdmin(Boolean(payload.user.is_admin));
        }
      })
      .catch(() => {
        if (!disposed) {
          setIsAdmin(false);
        }
      });
    return () => {
      disposed = true;
    };
  }, [pathname]);

  const navItems = hasToken ? [...AUTH_NAV_ITEMS, ...(isAdmin ? ADMIN_NAV_ITEMS : [])] : PUBLIC_NAV_ITEMS;

  return (
    <div className="min-h-screen px-4 py-4 md:px-6">
      <header className="mx-auto mb-4 w-[min(1200px,92vw)]">
        <div className="panel overflow-hidden">
          <div className="flex flex-col gap-4 p-4 md:flex-row md:items-center md:justify-between">
            <div className="grid gap-1">
              <p className="text-xs uppercase tracking-[0.08em] text-muted">Quant Trading</p>
              <h1 className="font-display text-xl">Ops Console</h1>
            </div>
            <nav className="flex flex-wrap gap-2">
              {navItems.map((item) => {
                const isActive = isActivePath(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-md px-3 py-2 text-sm transition-colors ${
                      isActive ? "bg-ink text-white" : "border border-black/10 bg-white hover:bg-black/5"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
              {hasToken ? (
                <button
                  className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
                  onClick={() => {
                    clearAuthSession();
                    setHasToken(false);
                    setIsAdmin(false);
                    router.push("/login");
                  }}
                >
                  Logout
                </button>
              ) : (
                <>
                  <Link
                    href="/login?next=%2Fdashboard"
                    className={`rounded-md px-3 py-2 text-sm transition-colors ${
                      pathname === "/login" ? "bg-ink text-white" : "border border-black/10 bg-white hover:bg-black/5"
                    }`}
                  >
                    Login
                  </Link>
                  <Link
                    href="/signup?next=%2Fdashboard"
                    className={`rounded-md px-3 py-2 text-sm transition-colors ${
                      pathname === "/signup" ? "bg-ink text-white" : "border border-black/10 bg-white hover:bg-black/5"
                    }`}
                  >
                    Sign Up
                  </Link>
                </>
              )}
            </nav>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
