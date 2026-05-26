"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { opsApi } from "../lib/api";
import { sendClientLog, toErrorMessage } from "../lib/client-log";
import { asDecimal, asInt, asKrw, asPct, asTime, short } from "../lib/format";
import type {
  AdminRuntimeSummaryItem,
  AdminUserBotStatusResponse,
  AdminUserCredentialResponse,
  AdminUserOrdersResponse,
  AdminUserPnlDailyResponse,
  AdminUserTradeMetricsResponse,
} from "../lib/types";

type BadgeTone = "green" | "amber" | "red" | "blue" | "gray";

type AdminUserDetailState = {
  bot: AdminUserBotStatusResponse;
  credential: AdminUserCredentialResponse;
  orders: AdminUserOrdersResponse;
  pnl: AdminUserPnlDailyResponse;
  metrics: AdminUserTradeMetricsResponse;
};

function badgeClass(tone: BadgeTone): string {
  return `status-badge status-badge-${tone}`;
}

function credentialLabel(credential: AdminUserCredentialResponse | AdminRuntimeSummaryItem["credential"]): {
  label: string;
  tone: BadgeTone;
} {
  if (!credential.has_credentials) {
    return { label: "미등록", tone: "amber" };
  }
  return credential.is_valid ? { label: "정상", tone: "green" } : { label: "확인 필요", tone: "red" };
}

function botTone(bot: AdminUserBotStatusResponse): BadgeTone {
  if (bot.halt_reason) return "amber";
  if (bot.is_enabled) return "green";
  return "gray";
}

function latestPnl(pnl: AdminUserPnlDailyResponse): AdminUserPnlDailyResponse["items"][number] | null {
  return pnl.items[0] ?? null;
}

export function AdminUserDetailPanel({
  accessToken,
  selectedUser,
  onClose,
  onAuthError,
}: {
  accessToken: string;
  selectedUser: AdminRuntimeSummaryItem | null;
  onClose: () => void;
  onAuthError?: (error: unknown) => boolean;
}) {
  const [detail, setDetail] = useState<AdminUserDetailState | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const loadDetail = useCallback(async () => {
    if (!accessToken || selectedUser === null) {
      setDetail(null);
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const [bot, credential, orders, pnl, metrics] = await Promise.all([
        opsApi.getAdminUserBotStatus({ accessToken, userId: selectedUser.user_id }),
        opsApi.getAdminUserCredential({ accessToken, userId: selectedUser.user_id }),
        opsApi.getAdminUserOrders({ accessToken, userId: selectedUser.user_id, limit: 8 }),
        opsApi.getAdminUserPnlDaily({ accessToken, userId: selectedUser.user_id, days: 14, tz: "KST" }),
        opsApi.getAdminUserTradeMetrics({ accessToken, userId: selectedUser.user_id, limit: 8 }),
      ]);
      setDetail({ bot, credential, orders, pnl, metrics });
    } catch (requestError) {
      if (onAuthError?.(requestError)) {
        return;
      }
      const message = toErrorMessage(requestError);
      setError(message);
      void sendClientLog({
        level: "ERROR",
        source: "admin-user-detail-panel.loadDetail",
        message,
        context: { target_user_id: selectedUser.user_id },
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, onAuthError, selectedUser]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const pnl = useMemo(() => (detail ? latestPnl(detail.pnl) : null), [detail]);
  const credential = detail ? credentialLabel(detail.credential) : credentialLabel(selectedUser?.credential ?? {
    has_credentials: false,
    is_valid: false,
    exchange: "UPBIT",
    key_version: null,
    access_key_masked: null,
    access_key_fingerprint_prefix: null,
    updated_at_utc: null,
  });

  if (selectedUser === null) {
    return (
      <section className="admin-panel">
        <div className="flex min-h-[180px] items-center justify-center rounded-xl border border-dashed border-[#e2e8f0] bg-[#f8fafc] p-6 text-center">
          <div>
            <p className="text-sm font-black text-ink">사용자를 선택하세요</p>
            <p className="mt-2 text-xs font-bold text-muted">
              운영 요약 표에서 상세 보기를 누르면 사용자별 봇, 인증, 주문, 손익, 체결 품질을 한곳에서 확인합니다.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="admin-panel" aria-live="polite">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">USER DETAIL</p>
          <h2 className="mt-1 font-display text-2xl font-black tracking-tight">
            {selectedUser.display_name || selectedUser.email}
          </h2>
          <p className="mt-1 text-xs font-bold text-muted">{selectedUser.email}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-secondary min-h-9 px-3 text-xs" onClick={() => void loadDetail()} disabled={isLoading}>
            {isLoading ? "불러오는 중..." : "새로고침"}
          </button>
          <button className="btn btn-secondary min-h-9 px-3 text-xs" onClick={onClose}>
            닫기
          </button>
        </div>
      </div>

      {error ? <p className="mt-3 rounded-xl border border-danger/30 bg-rose-50 p-3 text-sm text-danger">{error}</p> : null}

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <DetailKpi
          label="봇 상태"
          value={detail?.bot.status || selectedUser.bot.status}
          detail={detail?.bot.is_enabled ?? selectedUser.bot.is_enabled ? "활성" : "비활성"}
          tone={detail?.bot ? botTone(detail.bot) : selectedUser.bot.is_enabled ? "green" : "gray"}
        />
        <DetailKpi
          label="업비트 인증"
          value={credential.label}
          detail={detail?.credential.access_key_masked || selectedUser.credential.access_key_masked || "-"}
          tone={credential.tone}
        />
        <DetailKpi
          label="Risk / Halt"
          value={detail?.bot.halt_reason || selectedUser.halt.reason || "정상"}
          detail={`cooldown ${asTime(detail?.bot.cooldown_until_utc || selectedUser.halt.cooldown_until_utc, "ko-KR")}`}
          tone={detail?.bot.halt_reason || selectedUser.halt.reason ? "amber" : "green"}
        />
        <DetailKpi
          label="최근 손익"
          value={asKrw(pnl?.daily_pnl_abs, "ko-KR")}
          detail={asPct(pnl?.daily_pnl_pct, "ko-KR")}
          tone={(pnl?.daily_pnl_abs ?? 0) < 0 ? "red" : "green"}
        />
        <DetailKpi
          label="체결 품질"
          value={detail ? asInt(detail.metrics.count, "ko-KR") : "-"}
          detail="최근 체결 품질"
          tone="blue"
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-xl border border-line bg-white p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-black text-ink">최근 주문</h3>
            <span className={badgeClass("gray")}>{asInt(detail?.orders.count ?? 0, "ko-KR")}건</span>
          </div>
          <div className="mt-3 overflow-auto">
            <table className="admin-table min-w-[720px]">
              <thead>
                <tr>
                  <th>시장</th>
                  <th>방향</th>
                  <th>상태</th>
                  <th>의도</th>
                  <th>업데이트</th>
                  <th>메모</th>
                </tr>
              </thead>
              <tbody>
                {(detail?.orders.items ?? []).map((order) => (
                  <tr key={order.id}>
                    <td className="font-bold text-ink">{order.market}</td>
                    <td>{order.side}</td>
                    <td><span className={badgeClass(order.state === "ERROR_NEEDS_REVIEW" ? "red" : "gray")}>{order.state}</span></td>
                    <td>{order.intent || "-"}</td>
                    <td>{asTime(order.updated_at_kst || order.updated_at_utc, "ko-KR")}</td>
                    <td className="table-truncate" title={order.last_error || ""}>{short(order.last_error, 80)}</td>
                  </tr>
                ))}
                {detail && detail.orders.items.length === 0 ? (
                  <tr><td colSpan={6} className="text-sm text-muted">최근 주문이 없습니다.</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-xl border border-line bg-white p-4">
          <h3 className="text-sm font-black text-ink">운영 상태</h3>
          <dl className="mt-3 grid gap-3 text-xs">
            <InfoRow label="마지막 tick" value={asTime(detail?.bot.updated_at_kst || detail?.bot.updated_at_utc || selectedUser.bot.updated_at_utc, "ko-KR")} />
            <InfoRow label="일 손실 기준" value={detail?.bot.daily_loss_basis || "-"} />
            <InfoRow label="일 손실 한도" value={asPct(detail?.bot.max_daily_loss_pct, "ko-KR")} />
            <InfoRow label="주문 제한" value={`${asInt(detail?.bot.max_new_orders_per_day, "ko-KR")} / day, ${asInt(detail?.bot.max_orders_per_week, "ko-KR")} / week`} />
            <InfoRow label="목표 노출" value={asPct(detail?.bot.target_exposure_pct, "ko-KR")} />
            <InfoRow label="총 노출 한도" value={asPct(detail?.bot.max_total_exposure_pct, "ko-KR")} />
          </dl>
        </section>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <section className="rounded-xl border border-line bg-white p-4">
          <h3 className="text-sm font-black text-ink">최근 손익</h3>
          <div className="mt-3 overflow-auto">
            <table className="admin-table min-w-[680px]">
              <thead>
                <tr>
                  <th>날짜</th>
                  <th>평가 자산</th>
                  <th>일 손익</th>
                  <th>일 손익률</th>
                  <th>업데이트</th>
                </tr>
              </thead>
              <tbody>
                {(detail?.pnl.items ?? []).slice(0, 6).map((row) => (
                  <tr key={row.date}>
                    <td>{row.date}</td>
                    <td>{asKrw(row.last_equity, "ko-KR")}</td>
                    <td className={row.daily_pnl_abs < 0 ? "text-danger" : "text-safe"}>{asKrw(row.daily_pnl_abs, "ko-KR")}</td>
                    <td>{asPct(row.daily_pnl_pct, "ko-KR")}</td>
                    <td>{asTime(row.updated_at_kst || row.updated_at_utc, "ko-KR")}</td>
                  </tr>
                ))}
                {detail && detail.pnl.items.length === 0 ? (
                  <tr><td colSpan={5} className="text-sm text-muted">손익 데이터가 없습니다.</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-xl border border-line bg-white p-4">
          <h3 className="text-sm font-black text-ink">체결 품질</h3>
          <div className="mt-3 overflow-auto">
            <table className="admin-table min-w-[680px]">
              <thead>
                <tr>
                  <th>시장</th>
                  <th>방향</th>
                  <th>슬리피지</th>
                  <th>체결 시간</th>
                  <th>부분 체결</th>
                </tr>
              </thead>
              <tbody>
                {(detail?.metrics.items ?? []).map((row) => (
                  <tr key={`${row.order_id}-${row.created_at_utc || ""}`}>
                    <td>{row.market || "-"}</td>
                    <td>{row.side || "-"}</td>
                    <td>{asPct(row.slippage_pct, "ko-KR")}</td>
                    <td>{row.time_to_fill_ms === null ? "-" : `${asDecimal(row.time_to_fill_ms / 1000, "ko-KR", 2)}s`}</td>
                    <td>{asInt(row.partial_fill_count, "ko-KR")}</td>
                  </tr>
                ))}
                {detail && detail.metrics.items.length === 0 ? (
                  <tr><td colSpan={5} className="text-sm text-muted">체결 품질 데이터가 없습니다.</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </section>
  );
}

function DetailKpi({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: BadgeTone;
}) {
  return (
    <article className="rounded-xl border border-line bg-[#f8fafc] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{label}</p>
        <span className={badgeClass(tone)}>{label}</span>
      </div>
      <p className="mt-3 break-words font-display text-xl font-black text-ink">{value}</p>
      <p className="mt-1 break-words text-xs font-bold text-muted">{detail || "-"}</p>
    </article>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3">
      <dt className="font-bold text-muted">{label}</dt>
      <dd className="min-w-0 break-words font-black text-ink">{value || "-"}</dd>
    </div>
  );
}
