"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminAuditLogViewer } from "../../../components/admin-audit-log-viewer";
import { AdminUserDetailPanel } from "../../../components/admin-user-detail-panel";
import { AdminUsersRuntimeTable } from "../../../components/admin-users-runtime-table";
import { opsApi } from "../../../lib/api";
import type { AdminRuntimeSummaryItem } from "../../../lib/types";
import { toUserFacingErrorMessage } from "../../../lib/user-facing-error";
import { useAuthGuard } from "../../../lib/use-auth-guard";

export default function AdminOpsPage() {
  const router = useRouter();
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const [isVerifyingRole, setIsVerifyingRole] = useState(true);
  const [isAllowed, setIsAllowed] = useState(false);
  const [error, setError] = useState("");
  const [selectedUser, setSelectedUser] = useState<AdminRuntimeSummaryItem | null>(null);

  useEffect(() => {
    let disposed = false;
    const verifyRole = async () => {
      if (!isAuthReady || !accessToken) {
        return;
      }
      try {
        const payload = await opsApi.getMe({ accessToken });
        if (disposed) {
          return;
        }
        if (!payload.user.is_admin) {
          setIsAllowed(false);
          setIsVerifyingRole(false);
          router.replace("/dashboard");
          return;
        }
        setIsAllowed(true);
        setError("");
      } catch (requestError) {
        if (disposed) {
          return;
        }
        if (handleAuthError(requestError)) {
          return;
        }
        setIsAllowed(false);
        setError(toUserFacingErrorMessage(requestError, "admin"));
      } finally {
        if (!disposed) {
          setIsVerifyingRole(false);
        }
      }
    };
    void verifyRole();
    return () => {
      disposed = true;
    };
  }, [accessToken, handleAuthError, isAuthReady, router]);

  if (!isAuthReady || isVerifyingRole) {
    return (
      <main className="admin-console">
        <section className="admin-panel">
          <p className="text-sm text-muted">관리자 권한을 확인하는 중입니다.</p>
        </section>
      </main>
    );
  }

  if (!isAllowed) {
    return (
      <main className="admin-console">
        <section className="admin-panel">
          <p className="text-sm text-muted">
            {error || "관리자 권한이 필요합니다. 대시보드로 이동합니다."}
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="admin-console">
      <header className="page-header">
        <p className="text-xs font-black uppercase tracking-[0.08em] text-muted">ADMIN OPS</p>
        <div className="mt-1 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="font-display text-3xl font-black tracking-tight">관리자 운영</h1>
            <p className="mt-2 text-sm font-medium text-muted">
              사용자 런타임, 인증 상태, 위험 신호, 감사 로그를 확인합니다.
            </p>
          </div>
          <p className="text-xs font-bold text-muted">
            사용자별 상태와 관리자 작업은 `/api/admin/*` 권한 안에서만 조회됩니다.
          </p>
        </div>
      </header>

      <AdminUserDetailPanel
        accessToken={accessToken}
        selectedUser={selectedUser}
        onClose={() => setSelectedUser(null)}
        onAuthError={handleAuthError}
      />
      <AdminUsersRuntimeTable
        accessToken={accessToken}
        onAuthError={handleAuthError}
        onInspectUser={setSelectedUser}
        selectedUserId={selectedUser?.user_id ?? null}
      />
      <AdminAuditLogViewer accessToken={accessToken} onAuthError={handleAuthError} />
    </main>
  );
}
