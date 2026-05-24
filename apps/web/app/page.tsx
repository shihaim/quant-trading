"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { readAccessTokenOrEmpty } from "../lib/auth";
import { useLocale } from "../lib/locale";

export default function Page() {
  const router = useRouter();
  const { text } = useLocale();
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
      <main className="page">
        <section className="panel p-5">
          <p className="text-sm text-muted">{text.loadingAuth}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <section className="page-header overflow-hidden p-7 md:p-9">
        <div className="max-w-3xl">
          <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{text.product}</p>
          <h1 className="mt-2 font-display text-4xl font-black tracking-tight text-ink md:text-6xl">
            {text.appName}
          </h1>
          <p className="mt-5 text-lg font-black leading-8 text-ink md:text-xl">{text.entryIntro}</p>
          <p className="mt-3 text-base font-medium leading-7 text-muted">{text.landingDescription}</p>
        </div>
        <div className="mt-7 flex flex-wrap gap-2">
          <Link
            href="/login?next=%2Fdashboard"
            className="btn btn-primary"
          >
            {text.landingPrimary}
          </Link>
          <Link
            href="/signup?next=%2Fdashboard"
            className="btn btn-secondary"
          >
            {text.landingSecondary}
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="panel p-5">
          <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{text.riskFirst}</p>
          <p className="mt-2 text-2xl font-black tracking-tight text-ink">{text.guardedExecution}</p>
          <p className="mt-2 text-sm font-medium text-muted">{text.guardedExecutionDesc}</p>
        </article>
        <article className="panel p-5">
          <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{text.numbers}</p>
          <p className="mt-2 text-2xl font-black tracking-tight text-ink">{text.tabularMetrics}</p>
          <p className="mt-2 text-sm font-medium text-muted">{text.tabularMetricsDesc}</p>
        </article>
        <article className="panel p-5">
          <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{text.operations}</p>
          <p className="mt-2 text-2xl font-black tracking-tight text-ink">{text.cleanControlFlow}</p>
          <p className="mt-2 text-sm font-medium text-muted">{text.cleanControlFlowDesc}</p>
        </article>
      </section>
    </main>
  );
}

