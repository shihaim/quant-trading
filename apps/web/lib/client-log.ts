import { toUserFacingErrorMessage } from "./user-facing-error";

export type ClientLogLevel = "INFO" | "WARNING" | "ERROR";

type ClientLogInput = {
  level: ClientLogLevel;
  source: string;
  message: string;
  context?: Record<string, unknown>;
};

export async function sendClientLog(input: ClientLogInput): Promise<void> {
  try {
    await fetch("/api/logs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      keepalive: true
    });
  } catch {
    // Intentionally ignored to avoid cascading failures from logging.
  }
}

export function toErrorMessage(error: unknown): string {
  return toUserFacingErrorMessage(error);
}
