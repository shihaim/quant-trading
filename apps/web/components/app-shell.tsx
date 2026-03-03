"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/orders", label: "Orders" },
  { href: "/pnl", label: "PnL" },
  { href: "/execution", label: "Execution Metrics" },
  { href: "/control", label: "Bot Control" }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

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
              {NAV_ITEMS.map((item) => {
                const isActive = pathname === item.href;
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
            </nav>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
