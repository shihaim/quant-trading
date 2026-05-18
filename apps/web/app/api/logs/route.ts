import { appendFile, mkdir } from "node:fs/promises";
import path from "node:path";

import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const MAX_BODY_BYTES = 32 * 1024;

export async function POST(request: NextRequest) {
  try {
    const rawBody = await request.text();
    if (!rawBody) {
      return NextResponse.json({ ok: false, error: "empty_body" }, { status: 400 });
    }
    if (Buffer.byteLength(rawBody, "utf8") > MAX_BODY_BYTES) {
      return NextResponse.json({ ok: false, error: "payload_too_large" }, { status: 413 });
    }

    const logDir = process.env.WEB_LOG_DIR || path.join(process.cwd(), "logs");
    await mkdir(logDir, { recursive: true });

    let normalizedBody = rawBody;
    try {
      normalizedBody = JSON.stringify(JSON.parse(rawBody));
    } catch {
      // Preserve non-JSON payloads as-is.
    }

    const line = `${new Date().toISOString()} | ${normalizedBody}\n`;
    await appendFile(path.join(logDir, "client.log"), line, { encoding: "utf8" });

    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
