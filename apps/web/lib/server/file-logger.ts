import fs from "node:fs";
import path from "node:path";

export type FrontendLogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";

const LEVEL_WEIGHT: Record<FrontendLogLevel, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40
};

const DEFAULT_LOG_DIR = "./logs";
const DEFAULT_INFO_LOG_FILE = "web-info.log";
const DEFAULT_ERROR_LOG_FILE = "web-error.log";
const DEFAULT_LOG_LEVEL: FrontendLogLevel = "INFO";
const DEFAULT_ROTATE_MAX_BYTES = 10 * 1024 * 1024;
const DEFAULT_ROTATE_BACKUP_COUNT = 10;

function toLevel(raw: string | undefined): FrontendLogLevel {
  const normalized = String(raw || "").toUpperCase();
  if (normalized === "DEBUG" || normalized === "INFO" || normalized === "WARNING" || normalized === "ERROR") {
    return normalized;
  }
  return DEFAULT_LOG_LEVEL;
}

function toPositiveInt(raw: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(String(raw || ""), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

function resolveLogPath(level: FrontendLogLevel): string {
  const logDir = process.env.WEB_LOG_DIR || DEFAULT_LOG_DIR;
  const filename =
    level === "ERROR"
      ? process.env.WEB_ERROR_LOG_FILE || DEFAULT_ERROR_LOG_FILE
      : process.env.WEB_INFO_LOG_FILE || DEFAULT_INFO_LOG_FILE;
  return path.resolve(process.cwd(), logDir, filename);
}

function rotateIfNeeded(filePath: string, incomingBytes: number): void {
  const rotateMaxBytes = toPositiveInt(process.env.WEB_LOG_ROTATE_MAX_BYTES, DEFAULT_ROTATE_MAX_BYTES);
  const rotateBackupCount = toPositiveInt(process.env.WEB_LOG_ROTATE_BACKUP_COUNT, DEFAULT_ROTATE_BACKUP_COUNT);
  if (rotateBackupCount <= 0 || rotateMaxBytes <= 0) {
    return;
  }

  let currentBytes = 0;
  try {
    if (fs.existsSync(filePath)) {
      currentBytes = fs.statSync(filePath).size;
    }
  } catch {
    return;
  }

  if (currentBytes + incomingBytes <= rotateMaxBytes) {
    return;
  }

  for (let index = rotateBackupCount; index >= 1; index -= 1) {
    const fromPath = index === 1 ? filePath : `${filePath}.${index - 1}`;
    const toPath = `${filePath}.${index}`;
    if (!fs.existsSync(fromPath)) {
      continue;
    }
    try {
      if (fs.existsSync(toPath)) {
        fs.rmSync(toPath, { force: true });
      }
      fs.renameSync(fromPath, toPath);
    } catch {
      // Ignore rotation failures and continue with current file write.
    }
  }
}

export function writeFrontendLog(
  level: FrontendLogLevel,
  source: string,
  message: string,
  context?: Record<string, unknown>
): void {
  const configuredLevel = toLevel(process.env.WEB_LOG_LEVEL);
  if (LEVEL_WEIGHT[level] < LEVEL_WEIGHT[configuredLevel]) {
    return;
  }

  const filePath = resolveLogPath(level);
  const line =
    JSON.stringify({
      ts: new Date().toISOString(),
      level,
      source,
      message,
      context: context ?? {}
    }) + "\n";

  try {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    rotateIfNeeded(filePath, Buffer.byteLength(line));
    fs.appendFileSync(filePath, line, "utf8");
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    console.error(`[web-file-logger] failed to write log: ${reason}`);
  }
}
