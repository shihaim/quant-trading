import type {
  AuthTokenResponse,
  AuthUserIdentity,
  MeBotMutateResponse,
  MeBotStatusResponse,
  MeOrdersResponse,
  MePnlDailyResponse,
  MeTradeMetricsResponse,
  OpsSummary,
  PnlTimezone
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
export const ACCESS_TOKEN_STORAGE_KEY = "ops_access_token";

export class ApiRequestError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

function buildHeaders(headers: HeadersInit | undefined, accessToken?: string): Headers {
  const nextHeaders = new Headers(headers || {});
  if (!nextHeaders.has("Content-Type")) {
    nextHeaders.set("Content-Type", "application/json");
  }
  if (accessToken) {
    nextHeaders.set("Authorization", `Bearer ${accessToken}`);
  }
  return nextHeaders;
}

function withQuery(path: string, query: Record<string, string | number | null | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, String(value));
  });
  const serialized = params.toString();
  return serialized ? `${path}?${serialized}` : path;
}

async function request<T>(path: string, init?: RequestInit, accessToken?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: buildHeaders(init?.headers, accessToken),
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
    throw new ApiRequestError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function readStoredAccessToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY) ?? "";
}

export function writeStoredAccessToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
}

export function clearStoredAccessToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

export const opsApi = {
  signup: (payload: { email: string; password: string; display_name?: string }) =>
    request<AuthTokenResponse>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  login: (payload: { email: string; password: string }) =>
    request<AuthTokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getMe: ({ accessToken }: { accessToken: string }) => request<{ user: AuthUserIdentity }>("/api/me", undefined, accessToken),
  getSummary: ({ accessToken }: { accessToken: string }) => request<OpsSummary>("/api/ops/summary", undefined, accessToken),
  getMyOrders: ({
    accessToken,
    state,
    limit
  }: {
    accessToken: string;
    state?: string;
    limit?: number;
  }) => request<MeOrdersResponse>(withQuery("/api/me/orders", { state, limit }), undefined, accessToken),
  getMyPnlDaily: ({
    accessToken,
    days,
    tz
  }: {
    accessToken: string;
    days?: number;
    tz?: PnlTimezone;
  }) => request<MePnlDailyResponse>(withQuery("/api/me/pnl/daily", { days, tz }), undefined, accessToken),
  getMyTradeMetrics: ({
    accessToken,
    limit
  }: {
    accessToken: string;
    limit?: number;
  }) => request<MeTradeMetricsResponse>(withQuery("/api/me/metrics/trade", { limit }), undefined, accessToken),
  getMyBotStatus: ({ accessToken }: { accessToken: string }) =>
    request<MeBotStatusResponse>("/api/me/bot/status", undefined, accessToken),
  startMyBot: ({ accessToken }: { accessToken: string }) =>
    request<MeBotMutateResponse>("/api/me/bot/start", { method: "POST" }, accessToken),
  stopMyBot: ({ accessToken }: { accessToken: string }) =>
    request<MeBotMutateResponse>("/api/me/bot/stop", { method: "POST" }, accessToken)
};
