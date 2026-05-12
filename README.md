# inspection-engine
Reusable config-driven inspection engine (NRB + QuietRisk MVP)

All inspection behavior is driven by configuration (JSON). Deterministic rules produce classification/tags/patterns; PDFs are generated from pinned published versions.

**Public experience (handoff summary):** When no organization branding applies, the respondent UI and parent-facing PDF use the program name **SRI Program** and footer line **Structured Risk Inspection Technology**. Internal ownership references (for example in operating rules) are **not** used as public respondent or report footer copy. Already-submitted links show a **confirmation-style** state; technical IDs appear only under a collapsed **Reference details** area. Reports use **standard formatting** for classification labels and **plain consideration text** (no “Question 1 / Question 2” prefixes) while stored engine outputs remain unchanged.

### Local development (quick start)

#### Backend (Django)
From `backend/`:

```bash
pipenv install
pipenv run python manage.py migrate
pipenv run python manage.py createsuperuser
pipenv run python manage.py runserver 8000
```

Optional env vars (backend):
- `DEBUG=true`
- `FRONTEND_BASE_URL=http://localhost:5173`

Production on Render: see [docs/RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md) for env vars, build/start commands, and a short checklist.

#### Frontend (React/Vite)
From `frontend/`:

```bash
npm install
npm run dev
```

Optional env var (frontend):
- `VITE_API_BASE_URL` — local dev: defaults to `http://127.0.0.1:8000`. Production bundle built for Django-hosted SPA: omit this so the client uses same-origin `/api` (see deployment doc).

### Documentation

Primary review artifacts live in `docs/`:
- Architecture overview
- Config specification
- Rules engine definition
- Admin publish flow
- [Admin / operator handoff guide](guide.md) — non-developer handoff: wording, help text, versions, branding, reports, test submissions, EN/ES, safe vs unsafe edits; includes public respondent and PDF presentation notes
- Aggregation model (QuietRisk MVP)
- [SRI baseline template](docs/SRI_BASELINE.md) — seeded template instance and how to use it in admin
