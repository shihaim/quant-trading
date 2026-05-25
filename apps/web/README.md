# Don't worry, Be happy Web (Next.js)

Next.js + TypeScript + Tailwind frontend for the user dashboard and admin console.

## Structure

- `app/`: Next App Router pages and global styles
- `components/`: client components
- `lib/`: API client, types, format helpers

Primary routes:

- `/`: initial product entry page with login/signup navigation
- `/dashboard`: user account overview
- `/orders`: user order history
- `/pnl`: user profit and loss
- `/execution`: user execution quality
- `/control`: user bot control
- `/admin/ops`: admin operations console

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

For production Compose/Caddy deployment:

```bash
NEXT_PUBLIC_API_BASE_URL=
```

- Open `https://dont-worry-be-happy.today` or `https://www.dont-worry-be-happy.today`
- Leave `NEXT_PUBLIC_API_BASE_URL` empty so the browser uses same-origin `/api/*`

For local Caddy development:

- Open `https://qt-dashboard.local`
- Add a local hosts entry for `qt-dashboard.local` pointing to `127.0.0.1`
- Trust the Caddy local CA on your host OS if your browser warns about the certificate

## Local Preview Container

Use this when reviewing frontend changes without running the production web container.

- Backend preview API: `http://127.0.0.1:28080`
- Frontend preview URL: `http://127.0.0.1:3000`
- Frontend env: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:28080`
- Container name used in local review sessions: `qt-web-preview`

Keep preview credentials out of committed docs. Create or seed preview users through the local preview workflow when needed.

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
- Korean is the default language for new browsers.

## UX Copy Rules

- User pages must not expose raw API messages such as `API 401: invalid credentials`.
- Show friendly, actionable messages in Korean by default and English through the locale toggle.
- Admin pages may keep operational detail, but should still provide a short human-readable summary first.
