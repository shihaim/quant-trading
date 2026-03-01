# Ops Dashboard Web (Next.js)

Next.js + TypeScript + Tailwind frontend for the Ops dashboard.

## Structure

- `app/`: Next App Router pages and global styles
- `components/`: client components
- `lib/`: API client, types, format helpers

## Run

1. Start backend API:

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
```

2. Start frontend:

```bash
cd apps/web
npm install
npm run dev
```

3. Open:

- `http://127.0.0.1:3000`

## Environment

For direct local development:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080
```

For Compose/Caddy deployment:

```bash
NEXT_PUBLIC_API_BASE_URL=
```

- Open `https://qt-dashboard.local`
- Add a local hosts entry for `qt-dashboard.local` pointing to `127.0.0.1`
- Leave `NEXT_PUBLIC_API_BASE_URL` empty so the browser uses same-origin `/api/*`
- Trust the Caddy local CA on your host OS if your browser warns about the certificate

Frontend file logging (stored separately from backend logs):

```bash
WEB_LOG_DIR=./logs
WEB_INFO_LOG_FILE=web-info.log
WEB_ERROR_LOG_FILE=web-error.log
WEB_LOG_LEVEL=INFO
WEB_LOG_ROTATE_MAX_BYTES=10485760
WEB_LOG_ROTATE_BACKUP_COUNT=10
```

- Client-side errors are collected via `POST /api/logs` and written to files.
- With the default run command (`cd apps/web && npm run dev`), logs are written under `apps/web/logs`.
- Keep backend logs in the repo-root `logs/` directory to maintain frontend/backend separation.

## Language Support

- Supports both Korean and English in the dashboard UI.
- Use the language toggle in the header to switch.
- Selected language is saved in browser localStorage.
