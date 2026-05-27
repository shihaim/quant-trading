"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { opsApi } from "../lib/api";
import { sendClientLog, toErrorMessage } from "../lib/client-log";
import { asInt, asPct, asTime, short } from "../lib/format";
import type { AdminRuntimeSummaryItem, AdminRuntimeSummaryResponse } from "../lib/types";

type BadgeTone = "green" | "amber" | "red" | "blue" | "gray";
type PendingAdminAction =
  | { kind: "invalidate_sessions"; user: AdminRuntimeSummaryItem; confirmation: string }
  | { kind: "set_role"; user: AdminRuntimeSummaryItem; role: "admin" | "member"; confirmation: string }
  | null;

function badgeClass(tone: BadgeTone): string {
  return `status-badge status-badge-${tone}`;
}

function toCredentialLabel(item: AdminRuntimeSummaryItem): { label: string; tone: BadgeTone } {
  if (!item.credential.has_credentials) {
    return { label: "미등록", tone: "amber" };
  }
  return item.credential.is_valid ? { label: "정상", tone: "green" } : { label: "확인 필요", tone: "red" };
}

function toBotTone(item: AdminRuntimeSummaryItem): BadgeTone {
  if (item.flags.has_runtime_error) {
    return "red";
  }
  if (item.flags.is_halted) {
    return "amber";
  }
  if (item.bot.is_enabled) {
    return "green";
  }
  return "gray";
}

function toRiskLabel(item: AdminRuntimeSummaryItem): { label: string; tone: BadgeTone } {
  if (item.flags.is_budget_blocked) {
    return { label: "요청 제한", tone: "red" };
  }
  if (item.flags.is_halted) {
    return { label: "중지", tone: "amber" };
  }
  if (item.flags.has_runtime_error) {
    return { label: "오류", tone: "red" };
  }
  return { label: "정상", tone: "green" };
}

function toRowTone(item: AdminRuntimeSummaryItem): string {
  if (item.flags.is_budget_blocked || item.flags.has_runtime_error) {
    return "bg-rose-50/70";
  }
  if (item.flags.is_halted || item.flags.is_credential_invalid) {
    return "bg-amber-50/70";
  }
  return "";
}

function toLatestActivity(item: AdminRuntimeSummaryItem): string | null {
  return (
    item.activity.recent_action_at_utc ||
    item.activity.recent_error_at_utc ||
    item.activity.recent_order_at_utc ||
    item.activity.recent_audit_at_utc
  );
}

function countWhere(items: AdminRuntimeSummaryItem[], predicate: (item: AdminRuntimeSummaryItem) => boolean): number {
  return items.filter(predicate).length;
}

function sortRiskFirst(items: AdminRuntimeSummaryItem[]): AdminRuntimeSummaryItem[] {
  return [...items].sort((a, b) => {
    const score = (item: AdminRuntimeSummaryItem) =>
      Number(item.flags.is_budget_blocked) * 50 +
      Number(item.flags.has_runtime_error) * 40 +
      Number(item.flags.is_halted) * 30 +
      Number(item.flags.is_credential_invalid) * 20 +
      Number(!item.is_active) * 10;
    return score(b) - score(a);
  });
}

export function AdminUsersRuntimeTable({
  accessToken,
  onAuthError,
  onInspectUser,
  selectedUserId,
  onAuditFocus,
}: {
  accessToken: string;
  onAuthError?: (error: unknown) => boolean;
  onInspectUser?: (user: AdminRuntimeSummaryItem) => void;
  selectedUserId?: number | null;
  onAuditFocus?: (targetUserId: number) => void;
}) {
  const [payload, setPayload] = useState<AdminRuntimeSummaryResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [invalidatingUserId, setInvalidatingUserId] = useState<number | null>(null);
  const [roleUpdatingUserId, setRoleUpdatingUserId] = useState<number | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAdminAction>(null);
  const [actionMessage, setActionMessage] = useState("");

  const loadSummary = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const response = await opsApi.getAdminUsersRuntimeSummary({ accessToken, limit: 300 });
      setPayload(response);
      setError("");
    } catch (requestError) {
      if (onAuthError?.(requestError)) {
        return;
      }
      const message = toErrorMessage(requestError);
      setError(message);
      void sendClientLog({
        level: "ERROR",
        source: "admin-users-runtime-table.loadSummary",
        message,
        context: {},
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, onAuthError]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadSummary();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [loadSummary]);

  const canConfirmPendingAction =
    pendingAction !== null && pendingAction.confirmation.trim().toLowerCase() === pendingAction.user.email.toLowerCase();

  const completeSessionInvalidation = useCallback(
    async (user: AdminRuntimeSummaryItem) => {
      if (!accessToken || invalidatingUserId !== null || roleUpdatingUserId !== null) {
        return;
      }
      setInvalidatingUserId(user.user_id);
      setActionMessage("");
      try {
        const response = await opsApi.invalidateAdminUserSessions({
          accessToken,
          userId: user.user_id,
          reason: "admin_ops_session_invalidate",
        });
        setActionMessage(`${user.email} 세션을 무효화했습니다. 새 세션 버전: ${response.token_version}`);
        setPendingAction(null);
        onAuditFocus?.(user.user_id);
        await loadSummary();
      } catch (requestError) {
        if (onAuthError?.(requestError)) {
          return;
        }
        const message = toErrorMessage(requestError);
        setActionMessage(`세션 무효화 실패: ${message}`);
        void sendClientLog({
          level: "ERROR",
          source: "admin-users-runtime-table.invalidateUserSessions",
          message,
          context: { user_id: user.user_id },
        });
      } finally {
        setInvalidatingUserId(null);
      }
    },
    [accessToken, invalidatingUserId, loadSummary, onAuditFocus, onAuthError, roleUpdatingUserId]
  );

  const completeRoleUpdate = useCallback(
    async (user: AdminRuntimeSummaryItem, role: "admin" | "member") => {
      if (!accessToken || invalidatingUserId !== null || roleUpdatingUserId !== null) {
        return;
      }
      setRoleUpdatingUserId(user.user_id);
      setActionMessage("");
      try {
        const response = await opsApi.updateAdminUserRole({
          accessToken,
          userId: user.user_id,
          role,
        });
        const changedText = response.changed ? "변경하고 기존 세션을 무효화했습니다" : "이미 같은 역할이라 변경하지 않았습니다";
        setActionMessage(`${user.email} 역할을 ${response.role}로 ${changedText}.`);
        setPendingAction(null);
        onAuditFocus?.(user.user_id);
        await loadSummary();
      } catch (requestError) {
        if (onAuthError?.(requestError)) {
          return;
        }
        const message = toErrorMessage(requestError);
        setActionMessage(`역할 변경 실패: ${message}`);
        void sendClientLog({
          level: "ERROR",
          source: "admin-users-runtime-table.updateUserRole",
          message,
          context: { user_id: user.user_id, role },
        });
      } finally {
        setRoleUpdatingUserId(null);
      }
    },
    [accessToken, invalidatingUserId, loadSummary, onAuditFocus, onAuthError, roleUpdatingUserId]
  );

  const items = useMemo(() => sortRiskFirst(payload?.items ?? []), [payload?.items]);
  const summaryCards = [
    { label: "전체 사용자", value: asInt(payload?.count || 0), tone: "gray" as BadgeTone },
    { label: "실행 중", value: asInt(countWhere(items, (item) => item.bot.is_enabled)), tone: "green" as BadgeTone },
    {
      label: "중지/주의",
      value: asInt(countWhere(items, (item) => item.flags.is_halted || item.flags.is_budget_blocked)),
      tone: "amber" as BadgeTone,
    },
    {
      label: "인증 문제",
      value: asInt(countWhere(items, (item) => item.flags.is_credential_invalid || !item.credential.has_credentials)),
      tone: "red" as BadgeTone,
    },
    { label: "최근 오류", value: asInt(countWhere(items, (item) => item.flags.has_runtime_error)), tone: "red" as BadgeTone },
  ];

  return (
    <section className="grid gap-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {summaryCards.map((card) => (
          <article key={card.label} className="admin-panel">
            <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">{card.label}</p>
            <div className="mt-2 flex items-end justify-between gap-3">
              <p className="font-display text-3xl font-black tracking-tight">{card.value}</p>
              <span className={badgeClass(card.tone)}>{card.label}</span>
            </div>
          </article>
        ))}
      </div>

      <section className="admin-panel">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-display text-xl font-black tracking-tight">사용자 런타임</h2>
            <p className="mt-1 text-xs font-medium text-muted">
              위험, 중지, 인증 문제를 우선 정렬합니다. 최근 생성: {asTime(payload?.generated_at_kst || payload?.generated_at_utc, "ko-KR")}
            </p>
          </div>
          <p className="text-xs font-bold text-muted">{isLoading ? "불러오는 중..." : `${asInt(items.length, "ko-KR")}명 표시`}</p>
        </div>

        {error ? <p className="mb-3 rounded-xl border border-danger/30 bg-rose-50 p-3 text-sm text-danger">{error}</p> : null}
        {actionMessage ? (
          <div className="mb-3 flex flex-col gap-2 rounded-xl border border-safe/30 bg-emerald-50 p-3 text-xs font-bold text-ink md:flex-row md:items-center md:justify-between">
            <p>{actionMessage}</p>
            <a className="text-safe underline decoration-safe/50 underline-offset-4" href="#admin-audit-logs">
              감사 로그에서 확인
            </a>
          </div>
        ) : null}

        {pendingAction ? (
          <section className="mb-3 rounded-xl border border-amber-300 bg-amber-50 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-sm font-black text-ink">
                  {pendingAction.kind === "invalidate_sessions"
                    ? "세션 무효화 확인"
                    : `역할 변경 확인: ${pendingAction.role}`}
                </p>
                <p className="mt-1 text-xs font-bold text-muted">
                  위험한 관리자 작업입니다. 대상 계정 이메일을 정확히 입력해야 실행됩니다.
                </p>
                <p className="mt-2 text-xs text-muted">
                  대상: <strong>{pendingAction.user.email}</strong>
                </p>
              </div>
              <button className="btn btn-secondary min-h-9 px-3 text-xs" onClick={() => setPendingAction(null)}>
                취소
              </button>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-[1fr_auto]">
              <input
                className="form-control text-sm"
                placeholder={pendingAction.user.email}
                value={pendingAction.confirmation}
                onChange={(event) => setPendingAction({ ...pendingAction, confirmation: event.target.value })}
              />
              <button
                className="btn btn-primary min-h-10 px-4 text-xs"
                disabled={!canConfirmPendingAction || invalidatingUserId !== null || roleUpdatingUserId !== null}
                onClick={() => {
                  if (!canConfirmPendingAction) {
                    return;
                  }
                  if (pendingAction.kind === "invalidate_sessions") {
                    void completeSessionInvalidation(pendingAction.user);
                  } else {
                    void completeRoleUpdate(pendingAction.user, pendingAction.role);
                  }
                }}
              >
                확인 후 실행
              </button>
            </div>
          </section>
        ) : null}

        <div className="admin-table-wrap">
          <table className="admin-table admin-table-runtime">
            <colgroup>
              <col className="w-[260px]" />
              <col className="w-[170px]" />
              <col className="w-[200px]" />
              <col className="w-[180px]" />
              <col className="w-[260px]" />
              <col className="w-[190px]" />
              <col className="w-[220px]" />
            </colgroup>
            <thead>
              <tr className="text-left text-muted">
                <th>사용자</th>
                <th>봇 상태</th>
                <th>리스크</th>
                <th>인증</th>
                <th>최근 오류</th>
                <th>최근 활동</th>
                <th>작업</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const credential = toCredentialLabel(item);
                const risk = toRiskLabel(item);
                return (
                  <tr
                    key={item.user_id}
                    className={`${toRowTone(item)} ${selectedUserId === item.user_id ? "outline outline-2 outline-info/30" : ""}`}
                  >
                    <td>
                      <p className="table-truncate font-black text-ink" title={item.display_name || item.email}>{item.display_name || item.email}</p>
                      <p className="table-truncate text-xs text-muted" title={item.email}>{item.email}</p>
                      <p className="text-xs text-muted">user_id {item.user_id} / {item.role}</p>
                    </td>
                    <td>
                      <span className={badgeClass(toBotTone(item))}>{item.bot.status}</span>
                      <p className="mt-2 text-xs text-muted">{item.bot.is_enabled ? "활성" : "비활성"} / runtime {item.bot.runtime_status}</p>
                      <p className="text-xs text-muted">last tick {asTime(item.bot.last_tick_utc, "ko-KR")}</p>
                    </td>
                    <td>
                      <span className={badgeClass(risk.tone)}>{risk.label}</span>
                      <p className="mt-2 text-xs text-muted">{item.halt.reason || "halt 없음"}</p>
                      <p className="text-xs text-muted">
                        pnl {asPct(item.today_pnl.daily_pnl_pct, "ko-KR")} / threshold {asPct(item.today_pnl.halt_threshold_pct, "ko-KR")}
                      </p>
                    </td>
                    <td>
                      <span className={badgeClass(credential.tone)}>{credential.label}</span>
                      <p className="mt-2 text-xs text-muted">{item.credential.access_key_masked || "-"}</p>
                      <p className="text-xs text-muted">key {item.credential.key_version || "-"}</p>
                    </td>
                    <td>
                      {item.runtime.last_error ? (
                        <p className="table-truncate text-xs font-bold text-danger" title={item.runtime.last_error}>{short(item.runtime.last_error, 160)}</p>
                      ) : (
                        <span className={badgeClass("green")}>없음</span>
                      )}
                    </td>
                    <td>
                      <p className="text-xs text-ink">최근 {asTime(toLatestActivity(item), "ko-KR")}</p>
                      <p className="text-xs text-muted">order {asTime(item.activity.recent_order_at_utc, "ko-KR")}</p>
                      <p className="text-xs text-muted">audit {asTime(item.activity.recent_audit_at_utc, "ko-KR")}</p>
                    </td>
                    <td>
                      {onInspectUser ? (
                        <button
                          className="btn btn-primary mb-2 min-h-9 px-3 text-xs"
                          onClick={() => onInspectUser(item)}
                        >
                          상세 보기
                        </button>
                      ) : null}
                      <button
                        className="btn btn-secondary min-h-9 px-3 text-xs"
                        onClick={() => setPendingAction({ kind: "invalidate_sessions", user: item, confirmation: "" })}
                        disabled={invalidatingUserId !== null || roleUpdatingUserId !== null}
                      >
                        {invalidatingUserId === item.user_id ? "처리 중..." : "세션 무효화"}
                      </button>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          className="btn btn-secondary min-h-9 px-3 text-xs"
                          onClick={() => setPendingAction({ kind: "set_role", user: item, role: "admin", confirmation: "" })}
                          disabled={item.role === "admin" || invalidatingUserId !== null || roleUpdatingUserId !== null}
                        >
                          관리자로 변경
                        </button>
                        <button
                          className="btn btn-secondary min-h-9 px-3 text-xs"
                          onClick={() => setPendingAction({ kind: "set_role", user: item, role: "member", confirmation: "" })}
                          disabled={item.role !== "admin" || invalidatingUserId !== null || roleUpdatingUserId !== null}
                        >
                          일반으로 변경
                        </button>
                      </div>
                      <details className="mt-2">
                        <summary className="cursor-pointer text-xs font-bold text-muted">상세</summary>
                        <div className="mt-2 grid gap-1 text-xs text-muted">
                          <p>budget {asInt(item.budget.request_count, "ko-KR")} / {asInt(item.budget.limit, "ko-KR")}</p>
                          <p>blocked {asInt(item.budget.blocked_count, "ko-KR")} / remaining {asInt(item.budget.remaining, "ko-KR")}</p>
                          <p>cooldown {asTime(item.halt.cooldown_until_utc, "ko-KR")}</p>
                        </div>
                      </details>
                    </td>
                  </tr>
                );
              })}
              {!items.length && !isLoading ? (
                <tr>
                  <td className="text-sm text-muted" colSpan={7}>
                    표시할 사용자가 없습니다.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
