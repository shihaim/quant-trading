# P2 PnL/Risk Policy

## Scope

This document defines how the scheduler computes daily PnL for risk-halt decisions.

## Mark-to-Market Timing

- Evaluation timing: candle close at scheduler tick.
- Mark price source: latest completed candle close (`candles[-1].close`).
- Reason: reproducible backtest/live alignment and deterministic HALT behavior.

## Equity Formula

- `market_value = sum(position.qty * mark_price)`
- `equity = cash_krw + market_value`
- Daily TOTAL PnL:
  - `daily_pnl_abs = equity - start_equity`
  - `daily_pnl_pct = daily_pnl_abs / start_equity` (if `start_equity > 0`, else `0`)

## Daily Baseline

- Baseline key: UTC day (`daily_equity.date_utc`).
- On first run of a UTC day:
  - `start_equity = current_equity`
  - `start_realized_pnl = current_realized_pnl`
- During the same day:
  - baseline fields stay fixed
  - latest snapshots are updated

## `daily_loss_basis` Option

`bot_config.daily_loss_basis` supports:

- `TOTAL` (default)
  - Uses equity-based daily PnL (realized + unrealized).
- `REALIZED_ONLY`
  - Uses realized PnL delta only:
  - `realized_daily_abs = current_realized_pnl - start_realized_pnl`
  - `realized_daily_pct = realized_daily_abs / start_equity` (if `start_equity > 0`, else `0`)

## Risk Halt Rule

- Risk engine input: computed `daily_pnl_pct` by selected basis.
- Halt condition:
  - `daily_pnl_pct <= -abs(max_daily_loss_pct)`
- On halt, scheduler skips order creation and emits halt log/notification.

