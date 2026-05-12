## Frontend (React)

### Run

From `frontend/`:

```bash
npm install
npm run dev
```

By default, Vite proxies `/api/*` to `http://localhost:8000` (your Django backend).

The API client uses `VITE_API_BASE_URL` when set (non-empty). Otherwise, in **development** it calls `http://127.0.0.1:8000` directly; in **production builds** it uses the same origin as the page (empty base URL), which matches Django + WhiteNoise serving the SPA and `/api` together. The Vite dev proxy is optional if you prefer relative `/api` calls from the dev server.

### URL format

Open:

- `/{inspectionId}/{uuid}`

Example:

- `/demo/8b6f7c2e-1b2c-4b67-ae3b-6e52b30f4b6a`

### Optional env

If you want to hit a backend on a different origin (including local), set:

- `VITE_API_BASE_URL` (example: `http://127.0.0.1:8000` or `https://api.example.com`)


