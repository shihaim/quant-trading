import type { OpsSummary } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.message || data.error || detail;
    } catch {
      // ignore json parsing failures
    }
    throw new Error(`API ${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
}

export const opsApi = {
  getSummary: () => request<OpsSummary>("/api/ops/summary"),
  enableBot: () => request<{ is_enabled: boolean }>("/api/bot/enable", { method: "POST" }),
  disableBot: () => request<{ is_enabled: boolean }>("/api/bot/disable", { method: "POST" })
};
