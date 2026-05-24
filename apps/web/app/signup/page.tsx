"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";

import { opsApi, writeStoredAccessToken } from "../../lib/api";
import { normalizeNextPath, readAccessTokenOrEmpty } from "../../lib/auth";
import { useLocale } from "../../lib/locale";
import { toUserFacingErrorMessage } from "../../lib/user-facing-error";

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
  const { locale, text } = useLocale();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nextPath = useMemo(() => normalizeNextPath(searchParams.get("next"), "/dashboard"), [searchParams]);

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
      setError(toUserFacingErrorMessage(requestError, "signup", locale));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="page page-narrow">
      <section className="page-header p-6">
        <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{text.auth}</p>
        <h1 className="mt-2 font-display text-3xl font-black tracking-tight">{text.signup}</h1>
        <p className="mt-2 text-sm font-medium text-muted">{text.signupIntro}</p>

        <form className="mt-4 grid gap-3" onSubmit={(event) => void onSubmit(event)}>
          <label className="grid gap-1 text-sm text-muted">
            {text.email}
            <input
              className="form-control"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label className="grid gap-1 text-sm text-muted">
            {text.displayName}
            <input
              className="form-control"
              type="text"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
            />
          </label>
          <label className="grid gap-1 text-sm text-muted">
            {text.password}
            <input
              className="form-control"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <button
            className="btn btn-primary w-full"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? text.creatingAccount : text.createAccount}
          </button>
        </form>

        {error ? <p className="mt-3 rounded-md border border-danger/40 bg-rose-50 p-2 text-sm text-danger">{error}</p> : null}

        <div className="mt-4 flex flex-wrap gap-2 text-sm">
          <span className="text-muted">{text.alreadyHaveAccount}</span>
          <Link
            href={`/login?next=${encodeURIComponent(nextPath)}`}
            className="btn btn-secondary min-h-8 px-3"
          >
            {text.signIn}
          </Link>
        </div>
      </section>
    </main>
  );
}

function AuthPageFallback() {
  const { text } = useLocale();
  return (
    <main className="page page-narrow">
      <section className="panel p-5">
        <p className="text-sm text-muted">{text.loadingAuth}</p>
      </section>
    </main>
  );
}
