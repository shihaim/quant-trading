"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { readAccessTokenOrEmpty } from "../lib/auth";

export default function Page() {
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (readAccessTokenOrEmpty()) {
      router.replace("/dashboard");
      return;
    }
    setIsReady(true);
  }, [router]);

  if (!isReady) {
    return (
      <main className="mx-auto grid w-[min(980px,92vw)] gap-4 py-7">
        <section className="panel p-5">
          <p className="text-sm text-muted">Preparing entry page...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto grid w-[min(980px,92vw)] gap-4 py-7">
      <section className="panel p-6">
        <p className="text-xs uppercase tracking-[0.08em] text-muted">Quant Trading</p>
        <h1 className="mt-1 font-display text-3xl">V3 Ops Entry</h1>
        <p className="mt-3 text-sm text-muted">
          Public entry page. Sign in to access user-scoped dashboard and `/api/me/*` views. Admin-only ops summary is isolated at
          <code> /admin/ops</code>.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            href="/login?next=%2Fdashboard"
            className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
          >
            Login
          </Link>
          <Link
            href="/signup?next=%2Fdashboard"
            className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
          >
            Sign Up
          </Link>
        </div>
      </section>
    </main>
  );
}

