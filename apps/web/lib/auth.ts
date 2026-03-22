"use client";

import { clearStoredAccessToken, readStoredAccessToken } from "./api";

export type LoginReason = "expired" | "logged_out" | "unauthorized" | "revoked";

export function normalizeNextPath(raw: string | null | undefined, fallback = "/"): string {
  const value = String(raw || "").trim();
  if (!value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }
  return value;
}

export function buildLoginPath(nextPath: string, reason?: LoginReason): string {
  const next = encodeURIComponent(normalizeNextPath(nextPath, "/"));
  if (!reason) {
    return `/login?next=${next}`;
  }
  return `/login?next=${next}&reason=${encodeURIComponent(reason)}`;
}

export function readAccessTokenOrEmpty(): string {
  return readStoredAccessToken().trim();
}

export function clearAuthSession(): void {
  clearStoredAccessToken();
}
