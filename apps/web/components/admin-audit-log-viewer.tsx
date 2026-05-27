"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { opsApi } from "../lib/api";
import { sendClientLog, toErrorMessage } from "../lib/client-log";
import { asInt, asTime } from "../lib/format";
import type { AdminAuditLogsResponse } from "../lib/types";

type ResultFilter = "all" | "success" | "failure";

interface AuditFilters {
  actor_user_id: string;
  target_user_id: string;
  action: string;
  target_type: string;
  result: ResultFilter;
  from: string;
  to: string;
  limit: number;
}

const DEFAULT_LIMIT = 50;

function toIsoOrEmpty(value: string): string {
  if (!value.trim()) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return parsed.toISOString();
}

function toResultLabel(value: boolean | null): string {
  if (value === true) {
    return "성공";
  }
  if (value === false) {
    return "실패";
  }
  return "-";
}

function toResultClass(value: boolean | null): string {
  if (value === true) {
    return "status-badge status-badge-green";
  }
  if (value === false) {
    return "status-badge status-badge-red";
  }
  return "status-badge status-badge-gray";
}

export function AdminAuditLogViewer({
  accessToken,
  onAuthError,
  focusTargetUserId,
  focusNonce,
}: {
  accessToken: string;
  onAuthError?: (error: unknown) => boolean;
  focusTargetUserId?: number | null;
  focusNonce?: number;
}) {
  const [payload, setPayload] = useState<AdminAuditLogsResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState<AuditFilters>(() => {
    const now = new Date();
    const from = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    return {
      actor_user_id: "",
      target_user_id: "",
      action: "",
      target_type: "",
      result: "all",
      from: from.toISOString().slice(0, 16),
      to: now.toISOString().slice(0, 16),
      limit: DEFAULT_LIMIT,
    };
  });

  const requestParams = useMemo(
    () => ({
      actor_user_id: filters.actor_user_id ? Number(filters.actor_user_id) : undefined,
      target_user_id: filters.target_user_id ? Number(filters.target_user_id) : undefined,
      action: filters.action.trim() || undefined,
      target_type: filters.target_type.trim() || undefined,
      result: filters.result,
      from: toIsoOrEmpty(filters.from) || undefined,
      to: toIsoOrEmpty(filters.to) || undefined,
      limit: filters.limit,
      offset,
    }),
    [filters, offset]
  );

  const loadLogs = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const response = await opsApi.getAdminAuditLogs({
        accessToken,
        ...requestParams,
      });
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
        source: "admin-audit-log-viewer.loadLogs",
        message,
        context: {},
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, onAuthError, requestParams]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    if (!focusTargetUserId) {
      return;
    }
    setOffset(0);
    setFilters((prev) => ({
      ...prev,
      target_user_id: String(focusTargetUserId),
      action: "admin_action",
      result: "all",
    }));
  }, [focusNonce, focusTargetUserId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadLogs();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [loadLogs]);

  const canPrev = offset > 0;
  const canNext = Boolean(payload?.pagination.has_more);

  return (
    <section id="admin-audit-logs" className="admin-panel">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">AUDIT</p>
          <h2 className="mt-1 font-display text-xl font-black tracking-tight">감사 로그</h2>
          <p className="mt-2 text-sm font-medium text-muted">
            최근 운영 이벤트와 관리자 작업 결과를 확인합니다. 기본 조회 범위는 7일입니다.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-bold text-muted">
          <span className="status-badge status-badge-blue">최대 31일</span>
          <span className="status-badge status-badge-gray">15초 자동 갱신</span>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-4">
        <label className="grid gap-1 text-xs font-bold text-muted">
          행위자 ID
          <input
            className="form-control text-sm"
            inputMode="numeric"
            placeholder="예: 12"
            value={filters.actor_user_id}
            onChange={(event) => setFilters((prev) => ({ ...prev, actor_user_id: event.target.value }))}
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-muted">
          대상 사용자 ID
          <input
            className="form-control text-sm"
            inputMode="numeric"
            placeholder="예: 34"
            value={filters.target_user_id}
            onChange={(event) => setFilters((prev) => ({ ...prev, target_user_id: event.target.value }))}
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-muted">
          작업
          <input
            className="form-control text-sm"
            placeholder="action"
            value={filters.action}
            onChange={(event) => setFilters((prev) => ({ ...prev, action: event.target.value }))}
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-muted">
          대상 유형
          <input
            className="form-control text-sm"
            placeholder="target_type"
            value={filters.target_type}
            onChange={(event) => setFilters((prev) => ({ ...prev, target_type: event.target.value }))}
          />
        </label>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-4">
        <label className="grid gap-1 text-xs font-bold text-muted">
          결과
          <select
            className="form-control text-sm"
            value={filters.result}
            onChange={(event) => setFilters((prev) => ({ ...prev, result: event.target.value as ResultFilter }))}
          >
            <option value="all">전체</option>
            <option value="success">성공</option>
            <option value="failure">실패</option>
          </select>
        </label>
        <label className="grid gap-1 text-xs font-bold text-muted">
          시작
          <input
            className="form-control text-sm"
            type="datetime-local"
            value={filters.from}
            onChange={(event) => setFilters((prev) => ({ ...prev, from: event.target.value }))}
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-muted">
          종료
          <input
            className="form-control text-sm"
            type="datetime-local"
            value={filters.to}
            onChange={(event) => setFilters((prev) => ({ ...prev, to: event.target.value }))}
          />
        </label>
        <label className="grid gap-1 text-xs font-bold text-muted">
          표시 개수
          <input
            className="form-control text-sm"
            type="number"
            min={1}
            max={200}
            value={filters.limit}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                limit: Math.max(1, Math.min(200, Number(event.target.value) || DEFAULT_LIMIT)),
              }))
            }
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          className="btn btn-primary"
          onClick={() => {
            setOffset(0);
            void loadLogs();
          }}
        >
          필터 적용
        </button>
        <button className="btn" disabled={!canPrev} onClick={() => setOffset((prev) => Math.max(0, prev - filters.limit))}>
          이전
        </button>
        <button className="btn" disabled={!canNext} onClick={() => setOffset((prev) => prev + filters.limit)}>
          다음
        </button>
        <p className="text-xs font-bold text-muted">
          오프셋 {asInt(offset, "ko-KR")} / 반환 {asInt(payload?.pagination.returned || 0, "ko-KR")} / 스캔{" "}
          {asInt(payload?.scan.scanned_rows || 0, "ko-KR")}
        </p>
      </div>

      {error ? <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-bold text-red-700">{error}</p> : null}
      {isLoading && !payload ? <p className="mt-4 text-sm font-bold text-muted">감사 로그를 불러오는 중입니다.</p> : null}

      <div className="admin-table-wrap mt-5">
        <table className="admin-table admin-table-audit">
          <colgroup>
            <col className="w-[180px]" />
            <col className="w-[190px]" />
            <col className="w-[190px]" />
            <col className="w-[260px]" />
            <col className="w-[120px]" />
            <col className="w-[240px]" />
          </colgroup>
          <thead>
            <tr>
              <th>시각</th>
              <th>작업</th>
              <th>대상</th>
              <th>행위자</th>
              <th>결과</th>
              <th>상세</th>
            </tr>
          </thead>
          <tbody>
            {(payload?.items || []).map((item) => (
              <tr key={item.id}>
                <td>
                  <p className="font-bold">{asTime(item.created_at_utc, "ko-KR")}</p>
                  <p className="text-xs text-muted">id={item.id}</p>
                </td>
                <td>
                  <p className="table-truncate font-bold" title={item.action}>{item.action}</p>
                </td>
                <td>
                  <p className="table-truncate font-bold" title={item.target_type}>{item.target_type}</p>
                  <p className="text-xs text-muted">target_id={item.target_id || "-"}</p>
                  <p className="text-xs text-muted">target_user_id={item.target_user_id || "-"}</p>
                </td>
                <td>
                  <p className="table-truncate font-bold" title={item.actor_email || "-"}>{item.actor_email || "-"}</p>
                  <p className="text-xs text-muted">user_id={item.actor_user_id || "-"}</p>
                </td>
                <td>
                  <span className={toResultClass(item.is_success)}>{toResultLabel(item.is_success)}</span>
                </td>
                <td>
                  <details>
                    <summary className="cursor-pointer text-xs font-bold text-muted">메타데이터</summary>
                    <pre className="mt-2 max-w-[560px] overflow-auto whitespace-pre-wrap rounded bg-black/5 p-3 text-xs">
                      {JSON.stringify(item.metadata, null, 2)}
                    </pre>
                  </details>
                </td>
              </tr>
            ))}
            {!payload?.items?.length && !isLoading ? (
              <tr>
                <td className="text-sm font-bold text-muted" colSpan={6}>
                  현재 필터 범위에 감사 로그가 없습니다.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

