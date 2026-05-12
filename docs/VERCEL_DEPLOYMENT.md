# Vercel Deployment Guide (Frontend + Backend)

This repo is a monorepo with:
- `frontend/` (React + Vite SPA)
- `backend/` (Django API/admin/PDF service)

Best practice is to deploy as **two Vercel projects**:
1. Frontend project (root: `frontend`)
2. Backend project (root: `backend`)

---

## 1) Prerequisites

Before deployment, make sure you have:
- A GitHub repo connected to Vercel
- A production PostgreSQL database URL
- A production frontend domain name (from Vercel frontend project)
- A production backend domain name (from Vercel backend project)

---

## 2) Deploy Backend (Django) on Vercel

### A. Create backend Vercel project
1. In Vercel, click **Add New Project**.
2. Select this repository.
3. Set **Root Directory** to `backend`.
4. Framework preset: **Other** (Vercel auto-detects Python entry from `vercel.json`).

### B. Configure backend build
In project settings:
- **Build Command**:
  - `python manage.py collectstatic --no-input`
- **Output Directory**: leave empty
- **Install Command**: leave default (Vercel installs from `requirements.txt`)

### C. Set backend environment variables
Set these in Vercel Project Settings -> Environment Variables:

- `DEBUG=false`
- `SECRET_KEY=<strong-random-secret>`
- `DATABASE_URL=<postgres-url>`
- `ALLOWED_HOSTS=<your-backend-domain>`
- `FRONTEND_BASE_URL=<your-frontend-domain>`
- `CSRF_TRUSTED_ORIGINS=https://<your-frontend-domain>,https://<your-backend-domain>`
- `CORS_ALLOWED_ORIGINS=https://<your-frontend-domain>`

Optional:
- `RENDER_EXTERNAL_HOSTNAME` not needed on Vercel.

### D. Deploy backend
1. Click **Deploy**.
2. After deploy, test:
   - `https://<backend-domain>/api/health/`
   - `https://<backend-domain>/admin/`

### E. Run migrations (required)
Vercel serverless deploy does not reliably run one-off migrations as part of request flow.  
Run migrations manually from your machine against production DB:

```bash
cd backend
export DATABASE_URL="<postgres-url>"
export DEBUG=false
export SECRET_KEY="<same-secret>"
python -m pip install pipenv
pipenv install --deploy --ignore-pipfile
pipenv run python manage.py migrate
```

---

## 3) Deploy Frontend (Vite) on Vercel

### A. Create frontend Vercel project
1. In Vercel, click **Add New Project**.
2. Select this repository.
3. Set **Root Directory** to `frontend`.
4. Framework preset: **Vite** (auto-detected in most cases).

### B. Configure frontend environment variable
Set:
- `VITE_API_BASE_URL=https://<backend-domain>`

### C. Deploy frontend
1. Click **Deploy**.
2. Open frontend URL and validate:
   - Public form loads
   - Submit path reaches backend
   - No browser CORS/CSRF errors

---

## 4) Post-Deployment Verification Checklist

Backend checks:
- `/api/health/` returns `{ "ok": true }`
- Admin login works
- Static assets load on admin pages

End-to-end checks:
- Create a recipient link in admin
- Open public link from frontend domain
- Submit one response (or reopen an already-submitted link and confirm **confirmation-style** UI, not an error state)
- Confirm submission appears in admin
- Download parent PDF and confirm branding/language (default public branding: **SRI Program** / **Structured Risk Inspection Technology** when no org footer is configured)

---

## 5) Common Issues and Fixes

### 403 CSRF or CORS errors
- Re-check:
  - `CSRF_TRUSTED_ORIGINS`
  - `CORS_ALLOWED_ORIGINS`
  - frontend `VITE_API_BASE_URL`

### Admin styles missing
- Ensure backend build ran `collectstatic`.

### Database errors on deploy
- Ensure `DATABASE_URL` is valid and migrations were run.

### Frontend routes 404 on refresh
- `frontend/vercel.json` rewrite must be present (already included).

---

## 6) Notes

- Backend media storage is local/ephemeral in current stack; for durable uploaded files (for example branding logos in long-lived production), use persistent object storage in a future hardening pass.
- Current setup preserves all existing product behavior and business logic; this guide is deployment-oriented only.
