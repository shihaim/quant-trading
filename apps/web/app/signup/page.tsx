"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";

import { opsApi, writeStoredAccessToken } from "../../lib/api";
import { normalizeNextPath, readAccessTokenOrEmpty } from "../../lib/auth";

export default function SignupPage() {
  return (
    <Suspense fallback={<AuthPageFallback />}>
      <SignupPageInner />
    </Suspense>
  );
}

function SignupPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nextPath = useMemo(() => normalizeNextPath(searchParams.get("next"), "/orders"), [searchParams]);

  useEffect(() => {
    if (readAccessTokenOrEmpty()) {
      router.replace(nextPath);
    }
  }, [nextPath, router]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const payload = await opsApi.signup({
        email: email.trim(),
        password,
        display_name: displayName.trim() || undefined
      });
      writeStoredAccessToken(payload.access_token);
      setError("");
      router.replace(nextPath);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "failed to signup");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto grid w-[min(560px,92vw)] gap-4 py-7">
      <section className="panel p-5">
        <p className="text-xs uppercase tracking-[0.08em] text-muted">Authentication</p>
        <h1 className="mt-1 font-display text-2xl">Sign Up</h1>
        <p className="mt-2 text-sm text-muted">Create an account and continue directly to authenticated pages.</p>

        <form className="mt-4 grid gap-3" onSubmit={(event) => void onSubmit(event)}>
          <label className="grid gap-1 text-sm text-muted">
            Email
            <input
              className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm text-ink"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label className="grid gap-1 text-sm text-muted">
            Display Name (optional)
            <input
              className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm text-ink"
              type="text"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
            />
          </label>
          <label className="grid gap-1 text-sm text-muted">
            Password
            <input
              className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm text-ink"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <button
            className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Creating account..." : "Create Account"}
          </button>
        </form>

        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}

        <div className="mt-4 flex flex-wrap gap-2 text-sm">
          <span className="text-muted">Already have an account?</span>
          <Link
            href={`/login?next=${encodeURIComponent(nextPath)}`}
            className="rounded-md border border-black/10 bg-white px-2 py-1 transition-colors hover:bg-black/5"
          >
            Sign in
          </Link>
        </div>
      </section>
    </main>
  );
}

function AuthPageFallback() {
  return (
    <main className="mx-auto grid w-[min(560px,92vw)] gap-4 py-7">
      <section className="panel p-5">
        <p className="text-sm text-muted">Loading authentication...</p>
      </section>
    </main>
  );
}
