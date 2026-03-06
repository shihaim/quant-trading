"use client";

import { clearStoredAccessToken, readStoredAccessToken } from "./api";

export function normalizeNextPath(raw: string | null | undefined, fallback = "/"): string {
  const value = String(raw || "").trim();
  if (!value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }
  return value;
}

export function buildLoginPath(nextPath: string): string {
  return `/login?next=${encodeURIComponent(normalizeNextPath(nextPath, "/"))}`;
}

export function readAccessTokenOrEmpty(): string {
  return readStoredAccessToken().trim();
}

export function clearAuthSession(): void {
  clearStoredAccessToken();
}
