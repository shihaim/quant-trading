export interface OpsSummary {
  server_time_utc: string | null;
  server_time_kst: string | null;
  trade_mode: string;
  bot: {
    is_enabled: boolean;
    status: string;
    last_tick_utc: string | null;
    last_tick_kst: string | null;
  };
  halt: {
    is_halted: boolean;
    reason: string | null;
    triggered_at_utc: string | null;
    cooldown_until_utc: string | null;
    message: string | null;
  };
  config: {
    timeframe: string;
    markets: string[];
    daily_loss_basis: string;
    max_daily_loss_pct: number;
    max_weekly_loss_pct: number;
    max_monthly_loss_pct: number;
    cooldown_hours_on_halt: number;
    max_new_orders_per_day: number;
    max_orders_per_week: number;
    min_edge_pct: number;
    target_exposure_pct: number;
    max_total_exposure_pct: number;
    max_per_market_exposure_pct: number;
    min_rebalance_threshold_pct: number;
    min_order_krw_buffer: number;
    fill_timeout_sec_entry: number;
    fill_timeout_sec_exit: number;
    fill_timeout_sec_rebalance: number;
    max_reprice_attempts_entry: number;
    max_reprice_attempts_exit: number;
    max_reprice_attempts_rebalance: number;
    reprice_step_bps: number;
    slippage_budget_entry_pct: number;
    slippage_budget_exit_pct: number;
    slippage_budget_breach_halt_count: number;
    status_notify_interval_seconds: number;
    updated_at_utc: string | null;
  };
  risk_policy: {
    weekly_loss_pct: number;
    monthly_loss_pct: number;
    new_orders_today: number;
    orders_this_week: number;
  };
  today_pnl: {
    date_utc: string;
    start_equity: number;
    last_equity: number;
    realized_pnl: number;
    unrealized_pnl: number;
    daily_pnl_abs: number;
    daily_pnl_pct: number;
    start_realized_pnl: number;
    realized_daily_abs: number;
    realized_daily_pct: number;
    basis_used: string;
    halt_threshold_pct: number;
  };
  orders: {
    counts: {
      ERROR_NEEDS_REVIEW: number;
      OPEN: number;
      PARTIAL: number;
      IN_FLIGHT: number;
    };
    needs_review_top: Array<{
      id: number;
      updated_at_utc: string | null;
      market: string;
      side: string;
      intent: string | null;
      state: string;
      error_class: string | null;
      last_error: string | null;
      client_order_id: string;
      upbit_identifier: string | null;
      upbit_uuid: string | null;
    }>;
  };
  execution_quality: {
    kpi: {
      avg_slippage_pct: number | null;
      p95_slippage_pct: number | null;
      avg_time_to_fill_ms: number | null;
      avg_partial_fill_count: number | null;
    };
    budget: {
      entry_pct: number;
      exit_pct: number;
      breach_halt_count: number;
      breach_count_24h: number;
    };
    recent: Array<{
      order_id: number;
      executed_at_utc: string | null;
      market: string | null;
      side: string | null;
      intent: string | null;
      slippage_pct: number | null;
      time_to_fill_ms: number | null;
    }>;
  };
}

export type OperationalEventKind = "halt" | "credential_issue" | "order_review" | "runtime_error";
export type OperationalEventSeverity = "critical" | "warning" | "info";

export interface OperationalEvent {
  id: string;
  kind: OperationalEventKind;
  severity: OperationalEventSeverity;
  status: "open" | "resolved";
  occurred_at_utc: string | null;
  occurred_at_kst: string | null;
  title: string;
  message: string;
  action_label: string;
  action_view: string;
  detail?: Record<string, unknown>;
}

export interface AdminRuntimeSummaryItem {
  user_id: number;
  email: string;
  role: string;
  display_name: string | null;
  is_active: boolean;
  bot: {
    is_enabled: boolean;
    status: string;
    runtime_status: string;
    last_tick_utc: string | null;
    updated_at_utc: string | null;
  };
  runtime: {
    consecutive_failures: number;
    last_error: string | null;
  };
  halt: {
    is_halted: boolean;
    reason: string | null;
    triggered_at_utc: string | null;
    cooldown_until_utc: string | null;
    message: string | null;
  };
  budget: {
    scope: string;
    limit: number;
    window_seconds: number;
    window_started_at_utc: string | null;
    window_ends_at_utc: string | null;
    request_count: number;
    blocked_count: number;
    remaining: number;
    is_limited: boolean;
  };
  today_pnl: {
    daily_pnl_pct: number;
    halt_threshold_pct: number;
    weekly_loss_pct: number;
    monthly_loss_pct: number;
    new_orders_today: number;
    orders_this_week: number;
  };
  activity: {
    recent_order_at_utc: string | null;
    recent_audit_at_utc: string | null;
    recent_error_at_utc: string | null;
    recent_action_at_utc: string | null;
  };
  credential: {
    exchange: string;
    has_credentials: boolean;
    is_valid: boolean;
    key_version: string | null;
    access_key_masked: string | null;
    access_key_fingerprint_prefix: string | null;
    updated_at_utc: string | null;
  };
  flags: {
    is_halted: boolean;
    is_budget_blocked: boolean;
    has_runtime_error: boolean;
    is_credential_invalid: boolean;
    is_critical: boolean;
  };
  events: OperationalEvent[];
}

export interface AdminRuntimeSummaryResponse {
  generated_at_utc: string | null;
  generated_at_kst: string | null;
  count: number;
  items: AdminRuntimeSummaryItem[];
  source?: string;
  sort?: {
    strategy: string;
    fields: string[];
  };
}

export interface AdminAuditLogItem {
  id: number;
  created_at_utc: string | null;
  actor_user_id: number | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  target_user_id: number | null;
  is_success: boolean | null;
  metadata: Record<string, unknown>;
}

export interface AdminAuditLogsResponse {
  items: AdminAuditLogItem[];
  pagination: {
    limit: number;
    offset: number;
    returned: number;
    has_more: boolean;
  };
  scan: {
    scanned_rows: number;
    scan_capped: boolean;
    max_scan_rows: number;
  };
  filters: {
    actor_user_id: number | null;
    target_user_id: number | null;
    action: string | null;
    target_type: string | null;
    result: string;
    from_utc: string;
    to_utc: string;
  };
  source?: string;
}

export interface AdminSessionInvalidateResponse {
  user_id: number;
  token_version: number;
  invalidated_before_version: number;
  reason: string;
  source: string;
}

export interface AdminRoleUpdateResponse {
  user_id: number;
  role: "admin" | "member";
  is_admin: boolean;
  changed: boolean;
  token_version: number;
  invalidated_before_version: number | null;
  reason: string;
  source: string;
}

export interface AdminUserBotStatusResponse extends MeBotStatusResponse {
  user_id: number;
}

export interface AdminUserCredentialResponse extends MeUpbitCredentialResponse {
  user_id: number;
  source: string;
}

export interface AdminUserOrdersResponse extends MeOrdersResponse {
  user_id: number;
  source: string;
}

export interface AdminUserPnlDailyResponse extends MePnlDailyResponse {
  user_id: number;
  source: string;
}

export interface AdminUserTradeMetricsResponse extends MeTradeMetricsResponse {
  user_id: number;
  source: string;
}

export interface AuthUserIdentity {
  id: number;
  email: string;
  is_admin: boolean;
  display_name: string | null;
  is_active: boolean;
  created_at_utc: string | null;
  updated_at_utc: string | null;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUserIdentity;
}

export interface MeOverviewResponse {
  generated_at_utc: string | null;
  generated_at_kst: string | null;
  last_updated_utc: string | null;
  last_updated_kst: string | null;
  trade_mode: string;
  bot: {
    is_enabled: boolean;
    status: string;
    last_tick_utc: string | null;
    last_tick_kst: string | null;
    halt_reason: string | null;
    cooldown_until_utc: string | null;
    message: string | null;
  };
  credential: {
    exchange: string;
    has_credentials: boolean;
    is_valid: boolean;
    status_level: "connected" | "missing" | "needs_attention";
    next_action: "register_credentials" | "update_credentials" | null;
    key_version: string | null;
    access_key_masked: string | null;
    updated_at_utc: string | null;
    updated_at_kst: string | null;
  };
  today_pnl: {
    date_utc: string;
    last_equity: number;
    daily_pnl_abs: number;
    daily_pnl_pct: number;
    realized_daily_abs: number;
    realized_daily_pct: number;
  };
  orders: {
    needs_review_count: number;
    open_count: number;
    partial_count: number;
    in_flight_count: number;
  };
  events: OperationalEvent[];
}

export interface MeUpbitCredentialResponse {
  exchange: string;
  has_credentials: boolean;
  is_valid: boolean;
  status_level: "connected" | "missing" | "needs_attention";
  next_action: "register_credentials" | "update_credentials" | null;
  key_version: string | null;
  access_key_masked: string | null;
  access_key_fingerprint_prefix: string | null;
  updated_at_utc: string | null;
}

export interface ApiScope {
  mode: string;
  user_id: number;
}

export interface MeOrderItem {
  id: number;
  updated_at_utc: string | null;
  updated_at_kst: string | null;
  market: string;
  side: string;
  intent: string | null;
  state: string;
  error_class: string | null;
  last_error: string | null;
  client_order_id: string;
  upbit_identifier: string | null;
  upbit_uuid: string | null;
  attempt_no: number | null;
  attempt_submit_reason: string | null;
}

export interface MeOrdersResponse {
  count: number;
  items: MeOrderItem[];
  scope?: ApiScope;
}

export type PnlTimezone = "UTC" | "KST";

export interface MePnlDailyItem {
  date: string;
  start_equity: number;
  last_equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  daily_pnl_abs: number;
  daily_pnl_pct: number;
  start_realized_pnl: number;
  realized_daily_abs: number;
  realized_daily_pct: number;
  updated_at_utc: string | null;
  updated_at_kst: string | null;
}

export interface MePnlDailyResponse {
  tz: string;
  days: number;
  items: MePnlDailyItem[];
  scope?: ApiScope;
}

export interface MeTradeMetricItem {
  order_id: number;
  created_at_utc: string | null;
  created_at_kst: string | null;
  market: string | null;
  side: string | null;
  intent: string | null;
  intended_price: number | null;
  filled_vwap_price: number | null;
  slippage_abs: number | null;
  slippage_pct: number | null;
  fee_abs: number | null;
  time_to_fill_ms: number | null;
  partial_fill_count: number;
}

export interface MeTradeMetricsResponse {
  count: number;
  limit: number;
  items: MeTradeMetricItem[];
  scope?: ApiScope;
}

export interface MeBotStatusResponse {
  mode: string;
  status: string;
  is_enabled: boolean;
  halt_reason: string | null;
  halted_at_utc: string | null;
  halted_at_kst: string | null;
  cooldown_until_utc: string | null;
  cooldown_until_kst: string | null;
  daily_loss_basis: string;
  max_daily_loss_pct: number;
  max_weekly_loss_pct: number;
  max_monthly_loss_pct: number;
  cooldown_hours_on_halt: number;
  max_new_orders_per_day: number;
  max_orders_per_week: number;
  min_edge_pct: number;
  target_exposure_pct: number;
  max_total_exposure_pct: number;
  max_per_market_exposure_pct: number;
  updated_at_utc: string | null;
  updated_at_kst: string | null;
  source: string;
}

export interface MeBotMutateResponse {
  is_enabled: boolean;
  status?: string;
  halt_reason?: string | null;
  cooldown_until_utc?: string | null;
  cooldown_until_kst?: string | null;
  updated_at_utc: string | null;
  updated_at_kst: string | null;
  source: string;
}
