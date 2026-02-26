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

Set frontend API endpoint:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080
```

## Language Support

- Supports both Korean and English in the dashboard UI.
- Use the language toggle in the header to switch.
- Selected language is saved in browser localStorage.
