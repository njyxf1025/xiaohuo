# 会唱歌的数字人 · Frontend

React 18 + Vite 5 + TypeScript + TailwindCSS 3 frontend for the **Singing Digital
Human** app. Talks to the FastAPI backend (default `http://localhost:8000`).

## Stack

- React 18 + Vite 5
- TypeScript (strict)
- TailwindCSS 3 (dark mode default, brand purple/violet)
- React Router 6
- Zustand (with `localStorage` persistence)
- Axios (with `X-Request-ID` interceptor)
- wavesurfer.js 7
- react-dropzone
- sonner (toasts)
- lucide-react (icons)

## Develop

```bash
npm install
npm run dev
```

The dev server runs on http://localhost:5173 and proxies `/api/*` to
`http://localhost:8000`.

## Build

```bash
npm run build
```

Output is written to `dist/`. To preview the production build:

```bash
npm run preview
```

## Type-check / Lint

```bash
npm run typecheck
npm run lint
```

## Environment

Copy `.env.example` to `.env.local` to override the API base URL.

```env
VITE_API_BASE_URL=/api/v1
```

By default the dev server uses Vite's proxy, so `/api/v1/...` requests are
forwarded to the FastAPI backend running on port 8000.

## Routes

- `/` — Home (hero, system info, 4-step explainer)
- `/generate` — 4-step creator (upload → segment → avatar → generate)
- `/history` — past generation tasks with thumbnails & download links
