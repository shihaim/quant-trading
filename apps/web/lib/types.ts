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
    message: string | null;
  };
  config: {
    timeframe: string;
    markets: string[];
    daily_loss_basis: string;
    max_daily_loss_pct: number;
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

