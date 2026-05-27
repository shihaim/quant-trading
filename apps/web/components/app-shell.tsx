"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { opsApi } from "../lib/api";
import { buildLoginPath, clearAuthSession, readAccessTokenOrEmpty } from "../lib/auth";
import { LocaleProvider, type LocaleCode, useLocale } from "../lib/locale";

const APP_NAME = "Don't worry, Be happy";

type NavItem = {
  href: string;
  labelKey: "dashboard" | "orders" | "pnl" | "execution" | "control" | "adminOps";
  fallbackLabel?: string;
};

const AUTH_NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", labelKey: "dashboard" },
  { href: "/orders", labelKey: "orders" },
  { href: "/pnl", labelKey: "pnl" },
  { href: "/execution", labelKey: "execution" },
  { href: "/credentials", labelKey: "control", fallbackLabel: "업비트 인증" },
  { href: "/control", labelKey: "control" }
];

const ADMIN_NAV_ITEMS: NavItem[] = [{ href: "/admin/ops", labelKey: "adminOps" }];

function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <LocaleProvider>
      <AppShellContent>{children}</AppShellContent>
    </LocaleProvider>
  );
}

function AppShellContent({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { locale, setLocale, text } = useLocale();
  const [authToken, setAuthToken] = useState(() => readAccessTokenOrEmpty().trim());
  const [isAdmin, setIsAdmin] = useState(false);
  const hasToken = Boolean(authToken);

  useEffect(() => {
    setAuthToken(readAccessTokenOrEmpty().trim());
  }, [pathname]);

  useEffect(() => {
    let disposed = false;
    setIsAdmin(false);
    if (!authToken) {
      return () => {
        disposed = true;
      };
    }
    void opsApi
      .getMe({ accessToken: authToken })
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
  }, [authToken]);

  const navItems = [...AUTH_NAV_ITEMS, ...(isAdmin ? ADMIN_NAV_ITEMS : [])];

  return (
    <div className="min-h-screen bg-canvas text-ink md:flex">
      {hasToken ? (
        <aside className="hidden w-72 shrink-0 border-r border-[#e2e8f0] bg-white px-6 py-7 md:flex md:flex-col">
          <Link href="/dashboard" className="flex items-center gap-3">
            <Image
              src="/logo.png"
              alt={APP_NAME}
              width={206}
              height={100}
              className="h-16 w-auto max-w-full object-contain"
              priority
            />
          </Link>
          <nav className="mt-10 grid gap-1.5">
            {navItems.map((item) => {
              const isActive = isActivePath(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-xl px-4 py-3 text-sm font-bold transition-colors ${
                    isActive ? "bg-[#f1f5f9] text-ink" : "text-muted hover:bg-[#f8fafc] hover:text-ink"
                  }`}
                >
                  {item.fallbackLabel || text[item.labelKey]}
                </Link>
              );
            })}
          </nav>
        </aside>
      ) : null}

      <div className="min-w-0 flex-1 overflow-hidden px-4 py-4 md:px-8 lg:px-10">
        <header className="mx-auto mb-5 w-full max-w-[1200px]">
          <div className="panel overflow-hidden">
            <div className="flex flex-col gap-4 p-4 md:flex-row md:items-center md:justify-between">
              <Link href={hasToken ? "/dashboard" : "/"} className="flex min-w-0 items-center">
                <Image
                  src="/logo.png"
                  alt={APP_NAME}
                  width={206}
                  height={100}
                  className="h-14 w-auto max-w-[min(280px,70vw)] object-contain"
                  priority
                />
              </Link>
              <nav className="flex min-w-0 flex-wrap items-center gap-2">
                <LocaleSwitch locale={locale} setLocale={setLocale} />
                {hasToken ? (
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      clearAuthSession();
                      setAuthToken("");
                      setIsAdmin(false);
                      const safeNext = pathname && pathname.startsWith("/") ? pathname : "/dashboard";
                      router.push(buildLoginPath(safeNext, "logged_out"));
                    }}
                  >
                    {text.logout}
                  </button>
                ) : (
                  <>
                    <Link href="/login?next=%2Fdashboard" className="btn btn-secondary">
                      {text.login}
                    </Link>
                    <Link href="/signup?next=%2Fdashboard" className="btn btn-primary">
                      {text.signup}
                    </Link>
                  </>
                )}
              </nav>
            </div>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}

function LocaleSwitch({
  locale,
  setLocale
}: {
  locale: LocaleCode;
  setLocale: (locale: LocaleCode) => void;
}) {
  return (
    <div className="flex min-h-11 items-center rounded-2xl bg-[#f1f5f9] p-1">
      <button
        className={`flex min-h-9 items-center rounded-xl px-3 text-xs font-black ${
          locale === "ko" ? "bg-white text-ink shadow-sm" : "text-muted"
        }`}
        onClick={() => setLocale("ko")}
        type="button"
      >
        {locale === "ko" ? "한국어" : "KO"}
      </button>
      <button
        className={`flex min-h-9 items-center rounded-xl px-3 text-xs font-black ${
          locale === "en" ? "bg-white text-ink shadow-sm" : "text-muted"
        }`}
        onClick={() => setLocale("en")}
        type="button"
      >
        EN
      </button>
    </div>
  );
}
