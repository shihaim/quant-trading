"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { opsApi } from "../../lib/api";
import { asTime } from "../../lib/format";
import { useLocale, type LocaleCode } from "../../lib/locale";
import type { MeUpbitCredentialResponse } from "../../lib/types";
import { useAuthGuard } from "../../lib/use-auth-guard";
import { toUserFacingErrorMessage } from "../../lib/user-facing-error";

type CredentialCopy = {
  title: string;
  intro: string;
  status: string;
  connected: string;
  missing: string;
  needsAttention: string;
  connectedDetail: string;
  missingDetail: string;
  needsAttentionDetail: string;
  accessKey: string;
  secretKey: string;
  accessPlaceholder: string;
  secretPlaceholder: string;
  save: string;
  saving: string;
  refresh: string;
  updated: string;
  maskedAccess: string;
  safetyNote: string;
  success: string;
  loadError: string;
  lengthError: string;
};

const COPY: Record<LocaleCode, CredentialCopy> = {
  ko: {
    title: "업비트 인증",
    intro: "자동매매에 사용할 업비트 API 키를 등록하거나 갱신합니다.",
    status: "연결 상태",
    connected: "연결됨",
    missing: "미연결",
    needsAttention: "확인 필요",
    connectedDetail: "현재 저장된 인증 정보가 읽을 수 있는 상태입니다.",
    missingDetail: "자동매매를 시작하려면 업비트 API 키를 등록하세요.",
    needsAttentionDetail: "저장된 인증 정보를 읽을 수 없습니다. 새 키로 다시 저장하세요.",
    accessKey: "Access key",
    secretKey: "Secret key",
    accessPlaceholder: "업비트 Access key 입력",
    secretPlaceholder: "업비트 Secret key 입력",
    save: "저장",
    saving: "저장 중...",
    refresh: "새로고침",
    updated: "최근 저장",
    maskedAccess: "저장된 Access key",
    safetyNote: "Secret key는 저장 요청에만 사용되며 저장 후 화면에 다시 표시하지 않습니다.",
    success: "업비트 인증 정보가 저장되었습니다. Secret key는 다시 표시하지 않습니다.",
    loadError: "업비트 인증 상태를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    lengthError: "Access key와 Secret key는 각각 40자여야 합니다.",
  },
  en: {
    title: "Upbit Authentication",
    intro: "Register or update the Upbit API keys used for automated trading.",
    status: "Connection status",
    connected: "Connected",
    missing: "Not connected",
    needsAttention: "Needs attention",
    connectedDetail: "Stored authentication can be read by the service.",
    missingDetail: "Register Upbit API keys before starting automated trading.",
    needsAttentionDetail: "Stored authentication cannot be read. Save a fresh key pair.",
    accessKey: "Access key",
    secretKey: "Secret key",
    accessPlaceholder: "Enter Upbit Access key",
    secretPlaceholder: "Enter Upbit Secret key",
    save: "Save",
    saving: "Saving...",
    refresh: "Refresh",
    updated: "Last saved",
    maskedAccess: "Saved Access key",
    safetyNote: "The Secret key is used only for the save request and is never shown again after submission.",
    success: "Upbit authentication was saved. The Secret key will not be shown again.",
    loadError: "We could not load Upbit authentication status. Please try again shortly.",
    lengthError: "Access key and Secret key must each be 40 characters.",
  },
};

function statusLabel(status: MeUpbitCredentialResponse | null, copy: CredentialCopy): string {
  if (!status) return "-";
  if (status.status_level === "connected") return copy.connected;
  if (status.status_level === "needs_attention") return copy.needsAttention;
  return copy.missing;
}

function statusDetail(status: MeUpbitCredentialResponse | null, copy: CredentialCopy): string {
  if (!status) return copy.missingDetail;
  if (status.status_level === "connected") return copy.connectedDetail;
  if (status.status_level === "needs_attention") return copy.needsAttentionDetail;
  return copy.missingDetail;
}

function statusTone(status: MeUpbitCredentialResponse | null): "green" | "amber" | "red" {
  if (!status || status.status_level === "missing") return "amber";
  if (status.status_level === "needs_attention") return "red";
  return "green";
}

function badgeClass(tone: "green" | "amber" | "red"): string {
  if (tone === "green") return "status-badge status-badge-green";
  if (tone === "red") return "status-badge status-badge-red";
  return "status-badge status-badge-amber";
}

export default function CredentialsPage() {
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const { intlLocale, locale } = useLocale();
  const copy = COPY[locale];
  const [credential, setCredential] = useState<MeUpbitCredentialResponse | null>(null);
  const [accessKey, setAccessKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const loadCredential = useCallback(async () => {
    if (!isAuthReady || !accessToken) {
      setCredential(null);
      return;
    }
    setIsLoading(true);
    try {
      const nextCredential = await opsApi.getMyUpbitCredential({ accessToken });
      setCredential(nextCredential);
      setError("");
    } catch (requestError) {
      if (handleAuthError(requestError)) return;
      setError(copy.loadError);
      setCredential(null);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, copy.loadError, handleAuthError, isAuthReady]);

  useEffect(() => {
    if (!isAuthReady || !accessToken) return;
    void loadCredential();
  }, [accessToken, isAuthReady, loadCredential]);

  const keyLengthError = useMemo(() => {
    if (!accessKey.trim() && !secretKey.trim()) return "";
    if (accessKey.trim().length !== 40 || secretKey.trim().length !== 40) return copy.lengthError;
    return "";
  }, [accessKey, copy.lengthError, secretKey]);
  const canSubmit = useMemo(() => {
    return accessKey.trim().length === 40 && secretKey.trim().length === 40;
  }, [accessKey, secretKey]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isAuthReady || !accessToken || !canSubmit) {
      setError(keyLengthError || copy.lengthError);
      return;
    }
    setIsSaving(true);
    setNotice("");
    setError("");
    try {
      const saved = await opsApi.setMyUpbitCredential({
        accessToken,
        accessKey,
        secretKey,
      });
      setCredential(saved);
      setAccessKey("");
      setSecretKey("");
      setNotice(copy.success);
    } catch (requestError) {
      if (handleAuthError(requestError)) return;
      setError(toUserFacingErrorMessage(requestError, "generic", locale));
    } finally {
      setIsSaving(false);
    }
  }

  if (!isAuthReady) {
    return (
      <main className="page">
        <section className="panel p-5">
          <p className="text-sm text-muted">인증 상태를 확인하는 중...</p>
        </section>
      </main>
    );
  }

  const tone = statusTone(credential);

  return (
    <main className="page">
      <section className="page-header p-6 md:p-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">Upbit</p>
            <h1 className="mt-2 font-display text-4xl font-black tracking-tight text-ink">{copy.title}</h1>
            <p className="mt-3 text-sm font-medium text-muted">{copy.intro}</p>
          </div>
          <button className="btn btn-secondary" onClick={() => void loadCredential()} disabled={isLoading || isSaving}>
            {copy.refresh}
          </button>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <article className="data-panel p-6">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{copy.status}</p>
            <span className={badgeClass(tone)}>{statusLabel(credential, copy)}</span>
          </div>
          <p className="mt-4 text-sm font-bold text-ink">{statusDetail(credential, copy)}</p>
          <div className="mt-5 grid gap-3">
            <div>
              <p className="text-xs font-bold text-muted">{copy.maskedAccess}</p>
              <p className="mt-1 break-words text-lg font-black text-ink">{credential?.access_key_masked || "-"}</p>
            </div>
            <div>
              <p className="text-xs font-bold text-muted">{copy.updated}</p>
              <p className="mt-1 text-sm font-bold text-ink">{asTime(credential?.updated_at_utc, intlLocale)}</p>
            </div>
          </div>
        </article>

        <form className="data-panel p-6" onSubmit={handleSubmit}>
          <div className="grid gap-4">
            <label className="grid gap-2 text-sm font-bold text-ink">
              {copy.accessKey}
              <input
                className="form-control"
                value={accessKey}
                onChange={(event) => setAccessKey(event.target.value)}
                placeholder={copy.accessPlaceholder}
                autoComplete="off"
              />
            </label>
            <label className="grid gap-2 text-sm font-bold text-ink">
              {copy.secretKey}
              <input
                className="form-control"
                value={secretKey}
                onChange={(event) => setSecretKey(event.target.value)}
                placeholder={copy.secretPlaceholder}
                type="password"
                autoComplete="new-password"
              />
            </label>
            <p className="rounded-md border border-[#e2e8f0] bg-[#f8fafc] p-3 text-xs font-bold text-muted">
              {copy.safetyNote}
            </p>
            {notice ? <p className="rounded-md border border-safe/30 bg-emerald-50 p-3 text-sm font-bold text-safe">{notice}</p> : null}
            {keyLengthError ? (
              <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm font-bold text-amber-800">
                {keyLengthError}
              </p>
            ) : null}
            {error ? <p className="rounded-md border border-danger/40 bg-rose-50 p-3 text-sm font-bold text-danger">{error}</p> : null}
            <button className="btn btn-primary w-full" disabled={!canSubmit || isSaving || isLoading} type="submit">
              {isSaving ? copy.saving : copy.save}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
