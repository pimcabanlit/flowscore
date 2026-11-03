# FlowScore frontend (slice 4)

Next.js App Router, TypeScript strict, Tailwind. Spec: `docs/specs/04-frontend.md`; why it is
built this way: D25 in `docs/decisions.md`. Synthetic borrowers only; there is no sign-in.

The pages read the FastAPI backend and compute no figure themselves. The browser calls
`/api/v1/*` on this app's origin, and Next.js forwards it to `FLOWSCORE_API_URL`
(default `http://127.0.0.1:8000`). Rewrites are fixed at build time, so set the variable
before `npm run build` if the API runs elsewhere.

From the repository root, in PowerShell (Node 20.9 or later):

```powershell
.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"; $env:FLOWSCORE_DATABASE_URL="sqlite+aiosqlite:///flowscore-demo.db"
alembic upgrade head
python scripts\seed_demo_database.py
python scripts\assess_demo_borrowers.py
uvicorn backend.app.main:app                 # API on :8000; leave it running

# second terminal
cd frontend
npm ci
npm run build; npm start                     # http://localhost:3000 (or `npm run dev`)
```

Before a UI PR: `npm run check` (typecheck, lint, production build), then open the pages in a
browser and attach screenshots made with synthetic data only (`CLAUDE.md`).
