import "server-only";

import fs from "node:fs";
import path from "node:path";

export type FrontendLogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";

const LEVEL_TO_WEIGHT: Record<FrontendLogLevel, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40
};

type LoggerConfig = {
  minLevel: FrontendLogLevel;
  logDir: string;
  infoFile: string;
  errorFile: string;
  rotateMaxBytes: number;
  rotateBackupCount: number;
};

function parseLevel(raw: string | undefined): FrontendLogLevel {
  const normalized = String(raw || "INFO").toUpperCase();
  if (normalized === "DEBUG" || normalized === "INFO" || normalized === "WARNING" || normalized === "ERROR") {
    return normalized;
  }
  return "INFO";
}

function parsePositiveInt(raw: string | undefined, fallback: number, maxValue: number): number {
  const value = Number.parseInt(String(raw ?? ""), 10);
  if (!Number.isFinite(value) || value <= 0) {
    return fallback;
  }
  return Math.min(value, maxValue);
}

function getConfig(): LoggerConfig {
  return {
    minLevel: parseLevel(process.env.WEB_LOG_LEVEL || process.env.LOG_LEVEL),
    logDir: process.env.WEB_LOG_DIR || path.join(process.cwd(), "logs"),
    infoFile: process.env.WEB_INFO_LOG_FILE || "web-info.log",
    errorFile: process.env.WEB_ERROR_LOG_FILE || "web-error.log",
    rotateMaxBytes: parsePositiveInt(
      process.env.WEB_LOG_ROTATE_MAX_BYTES || process.env.LOG_ROTATE_MAX_BYTES,
      10 * 1024 * 1024,
      1024 * 1024 * 1024
    ),
    rotateBackupCount: parsePositiveInt(
      process.env.WEB_LOG_ROTATE_BACKUP_COUNT || process.env.LOG_ROTATE_BACKUP_COUNT,
      10,
      100
    )
  };
}

function shouldLog(level: FrontendLogLevel, minLevel: FrontendLogLevel): boolean {
  return LEVEL_TO_WEIGHT[level] >= LEVEL_TO_WEIGHT[minLevel];
}

function rotateIfNeeded(filePath: string, maxBytes: number, backupCount: number): void {
  if (!fs.existsSync(filePath)) {
    return;
  }
  const stat = fs.statSync(filePath);
  if (stat.size < maxBytes) {
    return;
  }
  if (backupCount <= 0) {
    fs.rmSync(filePath, { force: true });
    return;
  }
  const oldestPath = `${filePath}.${backupCount}`;
  if (fs.existsSync(oldestPath)) {
    fs.rmSync(oldestPath, { force: true });
  }
  for (let idx = backupCount - 1; idx >= 1; idx -= 1) {
    const src = `${filePath}.${idx}`;
    const dst = `${filePath}.${idx + 1}`;
    if (fs.existsSync(src)) {
      fs.renameSync(src, dst);
    }
  }
  fs.renameSync(filePath, `${filePath}.1`);
}

function sanitizeSingleLine(raw: unknown, maxLength: number): string {
  const text = String(raw ?? "");
  return text.replace(/\s+/g, " ").trim().slice(0, maxLength);
}

export function writeFrontendLog(
  level: FrontendLogLevel,
  source: string,
  message: string,
  context?: Record<string, unknown>
): void {
  const cfg = getConfig();
  if (!shouldLog(level, cfg.minLevel)) {
    return;
  }

  fs.mkdirSync(cfg.logDir, { recursive: true });
  const targetFile = level === "ERROR" ? cfg.errorFile : cfg.infoFile;
  const filePath = path.join(cfg.logDir, targetFile);
  rotateIfNeeded(filePath, cfg.rotateMaxBytes, cfg.rotateBackupCount);

  const safeSource = sanitizeSingleLine(source || "web", 80);
  const safeMessage = sanitizeSingleLine(message, 1000);
  const safeContext = context ? JSON.stringify(context).slice(0, 2000) : "";
  const line =
    `${new Date().toISOString()} | ${level} | ${safeSource} | ${safeMessage}` +
    (safeContext ? ` | ${safeContext}` : "") +
    "\n";
  fs.appendFileSync(filePath, line, { encoding: "utf-8" });
}
