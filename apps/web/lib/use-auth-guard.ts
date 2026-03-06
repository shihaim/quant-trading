"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ApiRequestError } from "./api";
import { buildLoginPath, clearAuthSession, readAccessTokenOrEmpty } from "./auth";

export function useAuthGuard() {
  const router = useRouter();
  const pathname = usePathname();
  const [accessToken, setAccessToken] = useState("");
  const [isAuthReady, setIsAuthReady] = useState(false);

  const nextPath = useMemo(() => (pathname && pathname.startsWith("/") ? pathname : "/"), [pathname]);

  useEffect(() => {
    const token = readAccessTokenOrEmpty();
    if (!token) {
      router.replace(buildLoginPath(nextPath));
      setIsAuthReady(false);
      return;
    }
    setAccessToken(token);
    setIsAuthReady(true);
  }, [nextPath, router]);

  const handleAuthError = (error: unknown): boolean => {
    if (error instanceof ApiRequestError && error.status === 401) {
      clearAuthSession();
      router.replace(buildLoginPath(nextPath));
      return true;
    }
    return false;
  };

  return { accessToken, isAuthReady, handleAuthError };
}
