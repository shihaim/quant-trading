"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminAuditLogViewer } from "../../../components/admin-audit-log-viewer";
import { AdminUsersRuntimeTable } from "../../../components/admin-users-runtime-table";
import { OpsDashboard } from "../../../components/ops-dashboard";
import { opsApi } from "../../../lib/api";
import { useAuthGuard } from "../../../lib/use-auth-guard";

export default function AdminOpsPage() {
  const router = useRouter();
  const { accessToken, isAuthReady, handleAuthError } = useAuthGuard();
  const [isVerifyingRole, setIsVerifyingRole] = useState(true);
  const [isAllowed, setIsAllowed] = useState(false);
  const [error, setError] = useState("");

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
        setError(requestError instanceof Error ? requestError.message : "failed to verify admin role");
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
      <main className="mx-auto grid w-[min(1200px,92vw)] gap-4 py-7">
        <section className="panel p-5">
          <p className="text-sm text-muted">Verifying access...</p>
        </section>
      </main>
    );
  }

  if (!isAllowed) {
    return (
      <main className="mx-auto grid w-[min(1200px,92vw)] gap-4 py-7">
        <section className="panel p-5">
          <p className="text-sm text-muted">
            {error || "You do not have admin access to this page. Redirecting to /dashboard."}
          </p>
        </section>
      </main>
    );
  }

  return (
    <>
      <OpsDashboard accessToken={accessToken} onAuthError={handleAuthError} />
      <section className="mx-auto grid w-[min(1200px,92vw)] gap-4 pb-7">
        <AdminUsersRuntimeTable accessToken={accessToken} onAuthError={handleAuthError} />
        <AdminAuditLogViewer accessToken={accessToken} onAuthError={handleAuthError} />
      </section>
    </>
  );
}
