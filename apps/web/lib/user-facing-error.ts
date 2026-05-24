import { ApiRequestError } from "./api";
import type { LocaleCode } from "./locale";

export type ErrorMessageContext =
  | "login"
  | "signup"
  | "auth"
  | "orders"
  | "pnl"
  | "execution"
  | "control"
  | "admin"
  | "generic";

type ErrorCopy = {
  fallback: Record<ErrorMessageContext, string>;
  network: string;
  invalidCredentials: string;
  duplicatedEmail: string;
  badInput: string;
  authRequired: string;
  notFound: string;
  conflict: string;
  rateLimited: string;
  server: string;
};

const ERROR_COPY: Record<LocaleCode, ErrorCopy> = {
  ko: {
    fallback: {
      login: "로그인하지 못했습니다. 입력한 정보를 확인한 뒤 다시 시도해 주세요.",
      signup: "계정을 만들지 못했습니다. 입력한 정보를 확인한 뒤 다시 시도해 주세요.",
      auth: "다시 로그인한 뒤 이용해 주세요.",
      orders: "주문 내역을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      pnl: "손익 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      execution: "체결 품질 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      control: "자동매매 상태를 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      admin: "관리자 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      generic: "일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
    },
    network: "서버에 연결하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도해 주세요.",
    invalidCredentials: "이메일 또는 비밀번호를 확인해 주세요.",
    duplicatedEmail: "이미 사용 중인 이메일입니다. 로그인하거나 다른 이메일을 입력해 주세요.",
    badInput: "입력한 정보를 다시 확인해 주세요.",
    authRequired: "다시 로그인한 뒤 이용해 주세요.",
    notFound: "요청한 정보를 찾지 못했습니다.",
    conflict: "이미 처리된 요청이거나 현재 상태와 맞지 않습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.",
    rateLimited: "요청이 많습니다. 잠시 후 다시 시도해 주세요.",
    server: "서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
  },
  en: {
    fallback: {
      login: "We could not sign you in. Please check your details and try again.",
      signup: "We could not create your account. Please check your details and try again.",
      auth: "Please sign in again to continue.",
      orders: "We could not load orders. Please try again shortly.",
      pnl: "We could not load profit and loss. Please try again shortly.",
      execution: "We could not load execution quality. Please try again shortly.",
      control: "We could not process automated trading status. Please try again shortly.",
      admin: "We could not load admin information. Please try again shortly.",
      generic: "Something went wrong. Please try again shortly."
    },
    network: "We could not reach the server. Please check your network and try again.",
    invalidCredentials: "Please check your email or password.",
    duplicatedEmail: "This email is already in use. Sign in or use another email.",
    badInput: "Please check the information you entered.",
    authRequired: "Please sign in again to continue.",
    notFound: "We could not find the requested information.",
    conflict: "This request was already handled or does not match the current state. Refresh and try again.",
    rateLimited: "Too many requests. Please try again shortly.",
    server: "The service is temporarily unavailable. Please try again shortly."
  }
};

function normalizeLocale(locale: LocaleCode | undefined): LocaleCode {
  return locale === "en" ? "en" : "ko";
}

function isNetworkLikeError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return message.includes("failed to fetch") || message.includes("network") || message.includes("load failed");
}

function hasInvalidCredentialsDetail(error: ApiRequestError): boolean {
  const detail = error.detail.toLowerCase();
  return detail.includes("invalid credentials") || detail.includes("incorrect") || detail.includes("unauthorized");
}

export function toUserFacingErrorMessage(
  error: unknown,
  context: ErrorMessageContext = "generic",
  locale?: LocaleCode
): string {
  const copy = ERROR_COPY[normalizeLocale(locale)];

  if (isNetworkLikeError(error)) {
    return copy.network;
  }

  if (!(error instanceof ApiRequestError)) {
    return copy.fallback[context];
  }

  if (context === "login" && error.status === 401 && hasInvalidCredentialsDetail(error)) {
    return copy.invalidCredentials;
  }

  if (context === "signup" && error.status === 409) {
    return copy.duplicatedEmail;
  }

  if (error.status === 400 || error.status === 422) {
    return copy.badInput;
  }

  if (error.status === 401 || error.status === 403) {
    return copy.authRequired;
  }

  if (error.status === 404) {
    return copy.notFound;
  }

  if (error.status === 409) {
    return copy.conflict;
  }

  if (error.status === 429) {
    return copy.rateLimited;
  }

  if (error.status >= 500) {
    return copy.server;
  }

  return copy.fallback[context];
}
