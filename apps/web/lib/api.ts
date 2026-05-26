import type {
  AdminAuditLogsResponse,
  AdminSessionInvalidateResponse,
  AdminUserBotStatusResponse,
  AdminUserCredentialResponse,
  AdminUserOrdersResponse,
  AdminUserPnlDailyResponse,
  AdminUserTradeMetricsResponse,
  AdminRuntimeSummaryResponse,
  AuthTokenResponse,
  AuthUserIdentity,
  MeBotMutateResponse,
  MeBotStatusResponse,
  MeOverviewResponse,
  MeOrdersResponse,
  MePnlDailyResponse,
  MeTradeMetricsResponse,
  MeUpbitCredentialResponse,
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
  getMyOverview: ({ accessToken }: { accessToken: string }) =>
    request<MeOverviewResponse>("/api/me/overview", undefined, accessToken),
  getMyUpbitCredential: ({ accessToken }: { accessToken: string }) =>
    request<MeUpbitCredentialResponse>("/api/me/credentials/upbit", undefined, accessToken),
  setMyUpbitCredential: ({
    accessToken,
    accessKey,
    secretKey,
  }: {
    accessToken: string;
    accessKey: string;
    secretKey: string;
  }) =>
    request<MeUpbitCredentialResponse>(
      "/api/me/credentials/upbit",
      {
        method: "POST",
        body: JSON.stringify({ access_key: accessKey, secret_key: secretKey }),
      },
      accessToken
    ),
  getSummary: ({ accessToken }: { accessToken: string }) => request<OpsSummary>("/api/ops/summary", undefined, accessToken),
  getAdminUsersRuntimeSummary: ({ accessToken, limit }: { accessToken: string; limit?: number }) =>
    request<AdminRuntimeSummaryResponse>(
      withQuery("/api/admin/users/runtime-summary", { limit }),
      undefined,
      accessToken
    ),
  getAdminUserBotStatus: ({ accessToken, userId }: { accessToken: string; userId: number }) =>
    request<AdminUserBotStatusResponse>(
      `/api/admin/users/${Math.max(1, Math.trunc(userId))}/bot/status`,
      undefined,
      accessToken
    ),
  getAdminUserCredential: ({ accessToken, userId }: { accessToken: string; userId: number }) =>
    request<AdminUserCredentialResponse>(
      `/api/admin/users/${Math.max(1, Math.trunc(userId))}/credentials/upbit`,
      undefined,
      accessToken
    ),
  getAdminUserOrders: ({
    accessToken,
    userId,
    state,
    limit,
  }: {
    accessToken: string;
    userId: number;
    state?: string;
    limit?: number;
  }) =>
    request<AdminUserOrdersResponse>(
      withQuery(`/api/admin/users/${Math.max(1, Math.trunc(userId))}/orders`, { state, limit }),
      undefined,
      accessToken
    ),
  getAdminUserPnlDaily: ({
    accessToken,
    userId,
    days,
    tz,
  }: {
    accessToken: string;
    userId: number;
    days?: number;
    tz?: PnlTimezone;
  }) =>
    request<AdminUserPnlDailyResponse>(
      withQuery(`/api/admin/users/${Math.max(1, Math.trunc(userId))}/pnl/daily`, { days, tz }),
      undefined,
      accessToken
    ),
  getAdminUserTradeMetrics: ({
    accessToken,
    userId,
    limit,
  }: {
    accessToken: string;
    userId: number;
    limit?: number;
  }) =>
    request<AdminUserTradeMetricsResponse>(
      withQuery(`/api/admin/users/${Math.max(1, Math.trunc(userId))}/metrics/trade`, { limit }),
      undefined,
      accessToken
    ),
  getAdminAuditLogs: ({
    accessToken,
    actor_user_id,
    target_user_id,
    action,
    target_type,
    result,
    from,
    to,
    limit,
    offset,
  }: {
    accessToken: string;
    actor_user_id?: number;
    target_user_id?: number;
    action?: string;
    target_type?: string;
    result?: "all" | "success" | "failure";
    from?: string;
    to?: string;
    limit?: number;
    offset?: number;
  }) =>
    request<AdminAuditLogsResponse>(
      withQuery("/api/admin/audit/logs", {
        actor_user_id,
        target_user_id,
        action,
        target_type,
        result,
        from,
        to,
        limit,
        offset,
      }),
      undefined,
      accessToken
    ),
  invalidateAdminUserSessions: ({
    accessToken,
    userId,
    reason,
  }: {
    accessToken: string;
    userId: number;
    reason?: string;
  }) =>
    request<AdminSessionInvalidateResponse>(
      `/api/admin/users/${Math.max(1, Math.trunc(userId))}/sessions/invalidate`,
      {
        method: "POST",
        body: JSON.stringify({ reason: reason || "admin_runtime_action" }),
      },
      accessToken
    ),
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
