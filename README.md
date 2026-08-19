# FleetFlow — Fleet Management & Logistics Tracking Platform

A centralized fleet management and logistics tracking platform: vehicles,
drivers, shipments, trips, route optimization, fuel, maintenance,
role-based access control, live tracking, notifications, analytics
dashboards, and PDF/Excel reporting — FastAPI backend, static JS frontend.

**This is the single, complete, final version of the project** — there is
only one `FleetFlow/` folder in this delivery, containing everything.

## Features

- **Auth & RBAC** — JWT login, 4 roles (Administrator, Fleet Manager,
  Dispatcher, Driver), enforced at the API level on every endpoint — not
  just hidden buttons. See **Role-based access control** below.
- **Fleet management** — vehicle registration, full CRUD, availability.
- **Driver management** — registration, full CRUD, attendance, performance.
- **Shipment tracking** — full lifecycle with validated state transitions
  (Created → Assigned → In Transit → Delayed → Delivered / Cancelled).
- **Route optimization** — 4 route types via Google Maps, with a free
  local distance/ETA estimator fallback when no API key is set.
- **Driver Dashboard** — a separate experience for Drivers: today's
  schedule, their own trips/shipments only, and a Start → Arrive →
  Complete workflow that updates shipment status automatically.
- **Live Tracking map** — Leaflet + OpenStreetMap (free, no API key),
  showing real pickup/destination/route for active shipments.
- **Dashboard & analytics** — 6 live, data-driven charts (Chart.js) plus
  KPI cards and operations tables. See **Charts** below.
- **Reports & export** — 5 report types, each exportable as PDF or Excel.
- **Admin User Management** — only Admins can create accounts or assign
  roles; self-registration is locked after the first account.
- **Demo data** — realistic, resettable, covering every status/role.

## Project structure

```
FleetFlow/
├── backend/
│   ├── app/
│   │   ├── models/            SQLAlchemy models
│   │   ├── schemas/           Pydantic schemas
│   │   ├── routers/           API endpoints, one file per module
│   │   ├── services/          auth, maps, notifications
│   │   ├── main.py            FastAPI app + router registration
│   │   ├── config.py          settings (env-driven)
│   │   ├── database.py        DB session/engine
│   │   ├── celery_app.py      Celery app + beat schedule
│   │   └── tasks.py           maintenance reminder task
│   ├── alembic/                 migrations (4, applied in order)
│   ├── seed_demo_data.py        demo data loader — see Demo data below
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── .env                     (gitignored — your real local config)
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── docker-compose.yml            full local stack in one command
├── render.yaml                   Render.com deployment blueprint
└── .gitignore
```

Plain HTML/CSS/JS frontend, no build step or framework — it calls the
FastAPI backend directly over HTTP/JSON.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic, Alembic, Uvicorn,
  Celery, JWT auth, httpx (Google Maps), reportlab (PDF), openpyxl (Excel)
- **Frontend:** HTML, CSS, vanilla JavaScript
- **Charts:** **Chart.js** (via CDN) — see the Charts section for why, and
  why it isn't a React library
- **Maps:** **Leaflet** + OpenStreetMap tiles (via CDN) — free, no key
- **Database:** PostgreSQL (primary), Redis (Celery broker)
- **Deployment:** Docker, Render (backend + Postgres), any static host for
  the frontend (Vercel/Netlify/GitHub Pages)

## 1. Install — Backend

```bash
cd FleetFlow/backend
python -m venv venv
source venv/Scripts/activate      # Windows Git Bash
# source venv/bin/activate        # macOS/Linux
pip install -r requirements.txt
```

## 2. Environment variables

Copy `.env.example` to `.env` (or edit the `.env` already included — it
only has placeholder values, no real secrets) and fill in your real
database password:

```
DATABASE_URL=postgresql://postgres:YOUR_ACTUAL_PASSWORD@localhost:5432/fleetflow_db
SECRET_KEY=pick-a-long-random-string-for-production
REDIS_URL=redis://localhost:6379/0
GOOGLE_MAPS_API_KEY=            # optional — leave blank for the free local route estimator
CORS_ORIGINS=*                  # optional — comma-separated allowed origins; lock down in production
```

If your password contains special characters like `@`, URL-encode them
(`@` → `%40`, `:` → `%3A`, `/` → `%2F`) or the connection string won't parse.

## 3. Database setup

```bash
psql -U postgres -c "CREATE DATABASE fleetflow_db;"
alembic upgrade head
```

This creates all tables via 4 migrations, applied in order.

## 4. Demo data

```bash
python seed_demo_data.py            # adds demo users + example shipments
python seed_demo_data.py --reset    # wipes all operational data and reloads fresh
```

Always run `--reset` after pulling an update to this project, so your
data matches the current models exactly.

## 5. Run the backend

```bash
uvicorn app.main:app --reload
```
Visit `http://127.0.0.1:8000/docs` for full interactive Swagger docs.

## 6. Run the frontend

```bash
cd FleetFlow/frontend
python -m http.server 5500
```
Open `http://127.0.0.1:5500`. It talks to `http://127.0.0.1:8000` by
default — see the top of `app.js` (`API_BASE`) to point it at a deployed
backend instead.

## 7. Celery (optional — maintenance reminders)

Requires Redis running locally.
```bash
celery -A app.celery_app worker --loglevel=info
celery -A app.celery_app beat --loglevel=info
```

## One-command local stack (Docker)

```bash
docker compose up --build
```
Runs Postgres, Redis, the backend, both Celery processes, and the static
frontend together. Backend at `:8000`, frontend at `:3000`.

## Demo login accounts

Created by `python seed_demo_data.py`:

| Role           | Username          | Password    | Notes |
|----------------|-------------------|-------------|-------|
| Administrator  | `admin_demo`      | `Demo@1234` | |
| Fleet Manager  | `manager_demo`    | `Demo@1234` | |
| Dispatcher     | `dispatcher_demo` | `Demo@1234` | |
| Driver         | `driver1_demo`    | `Demo@1234` | Linked to Driver Demo 1 — sees only SHP-1001 |
| Driver         | `driver2_demo`    | `Demo@1234` | Linked to Driver Demo 2 — sees only SHP-1002 |

**Self-registration is locked down.** The "First-time setup" tab on the
login screen only creates the very first Admin account on a brand-new,
empty database, and disappears once any account exists. Every account
after that comes from the in-app Admin → User Management page.

## Demo shipment locations

- **SHP-1001** — Chennai International Airport → Bengaluru, In Transit,
  Driver Demo 1, vehicle TN-01-AB-1234. Real coordinates both ends.
- **SHP-1002** — Hyderabad → Chennai, Assigned, Driver Demo 2, vehicle
  TN-02-CD-5678. Real coordinates both ends.
- SHP-1003/1004/1005 — supporting data (delivered/delayed/created) so
  every chart and table has real variety, not all zeros.

## Role-based access control

Enforced at the API level — a Driver calling `DELETE /vehicles/1`
directly gets a 403, regardless of what the frontend shows.

| Function | Admin | Fleet Manager | Dispatcher | Driver |
|---|---|---|---|---|
| Create/manage user accounts | Yes | No | No | No |
| Manage vehicles | Yes | Yes | No | No |
| View vehicles | Yes | Yes | Yes | No |
| Manage drivers | Yes | Yes | View/assign only | No |
| View own driver record | — | — | — | Yes (`/drivers/me`) |
| Manage shipments | Yes | Yes | Create/update status | View own only |
| Manage trips | Yes | Yes | Create/schedule | Own trips only |
| Trip workflow (start/arrive/complete) | — | — | — | Own trips only |
| Manage fuel records | Yes | Yes | No | Log own only |
| Manage maintenance | Yes | Yes | No | No |
| Dashboard / analytics | Yes | Yes | Yes | Own Driver Dashboard instead |
| Reports & export (PDF/Excel) | Yes | Yes | No | No |
| Live Tracking | Yes | Yes | Yes | Own trip only |

A Driver's account links to one `Driver` record (`User.driver_id`).
`/trips/` and `/shipments/` filter by that link at the database query
level — not hidden in the UI, actually filtered server-side. Fetching
another driver's record by ID returns 404.

## Charts

**Chart.js**, loaded via CDN. Not a React library — the frontend is
intentionally plain JS/HTML/CSS with no build step. Leaflet is used only
for the map; Chart.js only for the 6 dashboard charts — they don't overlap.

The 6 charts (`GET /dashboard/charts`, computed live from real data):
Fleet Utilization Trend (line), Vehicle Status Distribution (donut),
Shipment Delivery Performance (bar — Created/Assigned/In Transit/
Delayed/Delivered/Cancelled), Fuel Consumption (line), Delivery/ETA
Performance (pie), Maintenance Overview (bar — Upcoming/Overdue/Completed).
Each shows a specific "no data yet" message instead of an empty box when
a category genuinely has no data.

**Why the charts weren't rendering when reported as broken**, and what
was verified this pass: a real, headless browser-engine test (jsdom)
was built to execute the actual `app.js` against a running instance of
this exact backend, simulate a real login, and inspect the resulting
Chart.js configuration objects and any console/JS errors — not a
guess, an actual execution trace. Result: **all 6 charts rendered with
correct, non-empty, correctly-shaped data, and zero console or JS
errors.** The two most likely explanations for what was seen before:
(1) the duplicate `FleetFlow` / `FleetFlow_Complete` folders meant an
older, pre-fix copy of the frontend was what the browser was actually
loading — this delivery has only one folder, eliminating that; (2) a
browser cache holding an old `app.js`. If charts still don't render
after using this exact package fresh, open the browser DevTools console
— the error message shown will now be specific (e.g. the real HTTP
status/detail) instead of generic, which will point at the real cause.

Also hardened while investigating: the fuel/utilization trend queries
used a legacy raw-string `.group_by("day")` pattern (SQLAlchemy
deprecation, not a runtime failure) — rewritten to use explicit column
references, which is dialect-safer across SQLite and PostgreSQL.

## Assignment → Notification → Status → Live Tracking → Completion workflow

The core feature of this pass — persisted entirely through the backend/
database, not frontend-only state.

**Assignment.** An Admin/Manager/Dispatcher assigns work by creating a
`Trip` (`POST /trips/`, linking a driver + vehicle + optionally shipment
IDs) or by setting `dispatcher_user_id` on a shipment
(`PUT /shipments/{id}`). Both fire real notifications immediately:
- The **driver's own linked User account** (via `User.driver_id`) gets a
  notification with pickup, destination, vehicle, and scheduled time.
- The **specific dispatcher** (if `dispatcher_user_id` is set) gets a
  targeted notification; otherwise it broadcasts to the Dispatcher role
  so dispatch isn't left blind.

**Status workflow.** `Scheduled → In Progress → (Arrived) → Completed`
on the Trip, cascading to the Shipment (`Assigned → In Transit →
Delivered`). Every status change is recorded in a `status_history` table
(`GET /shipments/{id}/history`, `GET /trips/{id}/history`) — not just
overwritten — so reports/ETA analysis have the full timeline, not just
the current state.

**Live location tracking.** The Driver Dashboard uses the browser's
`navigator.geolocation.watchPosition` — real device location, not
simulated — and polls `POST /tracking/location` every 20 seconds while a
trip is in progress. This is deliberately polling, not a persistent
WebSocket, so it works unmodified on Vercel's serverless functions (see
**Vercel deployment** below). `GET /tracking/trip/{id}` and
`GET /tracking/active` (the Dispatcher/Manager "Active Trips" table) read
the latest position back. If location permission is denied, the app
shows a plain message and the trip still proceeds — it never crashes,
and never claims real GPS when it only has an estimate.

**Completion.** `POST /trips/{id}/complete` takes a required completion
note (and lat/lng if the browser has one), driver-only, ownership-checked.
It sets `completed_at`, `completed_by`, `completion_note`,
`completion_lat/lng` on the Shipment, marks it Delivered, and notifies
both Admin+Manager and the responsible Dispatcher with the note included.

**Delete.** Admin/Manager only, never Driver (enforced server-side, not
just a hidden button). Soft delete (`deleted`/`deleted_at`/`deleted_by`
columns) — records aren't destroyed, just excluded from operational
lists and analytics. A Shipment can only be deleted once it's Delivered
or Cancelled (an active one gets cancelled first); a Trip can only be
deleted once Completed or Cancelled. The frontend always confirms before
deleting ("Delete Shipment? ... This action cannot be undone").

**Security**, tested with live requests, not assumed: a Driver
submitting another driver's location → 403; viewing another driver's
trip tracking → 404; deleting a shipment → 403; a Manager creating a
user → 403. See Testing below for the exact checks run.

## Live Tracking map

Leaflet + OpenStreetMap tiles — free, no API key. Plots real pickup/
destination coordinates from `Route` records tied to each trackable
shipment, draws the route line, and places a vehicle marker. That marker
now prefers **real location** reported by the driver's browser
(`has_live_location: true`, with "last updated Xs ago") and only falls
back to an elapsed-time **estimate** along the route when no real
location has been reported yet — never labeled as live when it isn't.
For a Driver, this automatically shows only their own trip. The
Dispatcher/Manager Tracking page also shows an **Active Trips** table
(Trip / Driver / Shipment / Status / Last Location) above the map —
clicking a row centers the map on that trip.

Verified this pass with the same jsdom execution-trace method as the
charts: logged in as a Dispatcher, opened Live Tracking, and confirmed
the Active Trips table renders real trip/driver/shipment data from the
live backend.

## Testing — what was actually run, and the result

| Check | Result |
|---|---|
| Fresh `alembic upgrade head` (4 migrations) + `alembic check` | Pass — applies cleanly, zero drift from models |
| `seed_demo_data.py` fresh load | Pass |
| **Real jsdom execution trace**: login → dashboard → all 6 charts | Pass — actual `app.js` executed against the live backend; verified real Chart.js config objects (correct labels/data per chart), zero console errors, zero unhandled JS exceptions |
| **Real jsdom execution trace**: Live Tracking map | Pass — 6 markers, 2 routes, correct popups for both demo shipments |
| **Real jsdom execution trace**: Driver role sidebar + bypass attempt | Pass — all restricted nav items correctly hidden for a Driver login; a direct programmatic call to `loadView('vehicles')` as a Driver was redirected back to the Driver Dashboard, not allowed through |
| Backend RBAC (curl, per role) | Pass — Driver `DELETE /vehicles/1` → 403; Driver fetching another driver's shipment by ID → 404; Manager creating a user → 403; self-registration after first account → 403 |
| Driver trip workflow (start/arrive/complete) | Pass — ownership check, status transitions, cascading shipment status, all verified live |
| Admin user creation/disable/reset-password | Pass — created a driver-linked user via the exact payload the UI sends, disabled it, confirmed login then correctly fails |
| PDF/Excel export (5 report types) | Pass — valid files produced |

**Not tested / could not be tested in this environment, told to you
plainly rather than guessed at:**
- **Real Postgres** — this sandbox has no working Postgres install (its
  package mirror returned 404s). Everything above was tested against
  SQLite. The SQL was hardened to avoid a legacy pattern that could
  theoretically behave differently across dialects, but this is not the
  same as having run it against Postgres directly. Test on your own
  Postgres instance and tell me if anything differs.
- **Real browser rendering (pixels/CSS layout)** — jsdom proves the JS
  logic, data, and DOM state are all correct, but it doesn't render
  actual pixels. Do a visual pass yourself, especially responsive
  breakpoints on real devices.
- **Live Google Maps API calls** — this sandbox can't reach
  `googleapis.com`. The fallback local estimator was what all testing
  used; the live-key code path is implemented but unverified.
- **Real Docker/cloud deployment** — no Docker daemon or cloud
  credentials available here. Deployment configs are written correctly
  per each platform's documented format, but the first real deploy is
  yours to run.

### This pass — assignment/notification/tracking/completion workflow

| Check | Result |
|---|---|
| 5 migrations fresh + `alembic check` | Pass — zero drift |
| Assignment fires driver + dispatcher notifications with full details | Pass — verified via live API calls: created a shipment, set a dispatcher, created a trip linking a driver+vehicle+shipment, confirmed both the driver's own account and the dispatcher received notifications with pickup/destination/vehicle/schedule |
| Full workflow: start → location → tracking → arrive → complete-with-note | Pass — verified live: trip started, location submitted and read back via `/tracking/trip/{id}`, arrival marked, completion with note+coordinates saved on the shipment (`completed_at`, `completed_by`, `completion_note`, `completion_lat/lng` all correct) |
| Manager + Dispatcher notified on completion, with the note included | Pass |
| Status history recorded (not just overwritten) | Pass — `/shipments/{id}/history` and `/trips/{id}/history` return the full timeline |
| Security: driver can't submit/view another driver's location or trip | Pass — 403 / 404 respectively |
| Security: driver can't delete anything | Pass — 403 |
| Soft delete: shipment/trip excluded from lists + analytics after delete | Pass — confirmed a deleted shipment disappeared from `/shipments/` and from `/dashboard/charts` shipment-status counts |
| Delete only allowed once Delivered/Cancelled (shipment) or Completed/Cancelled (trip) | Pass — deleting an active trip correctly returns 400 |
| **Real jsdom execution trace**: Driver dashboard → Mark Arrived → Complete Delivery modal → submit | Pass — found and fixed a real bug in this pass: the completion form read `form.completion_note.value` (relying on HTML's named-form-control auto-binding), which isn't reliable for `<textarea>` across engines — changed to an explicit `querySelector`, then re-verified the full flow completes with zero JS errors |
| **Real jsdom execution trace**: Admin → Shipments → Delete button → confirmation modal | Pass — confirmed the modal shows the specific tracking number and requires a second click |
| **Real jsdom execution trace**: Dispatcher → Live Tracking → Active Trips table | Pass — confirmed real trip/driver/shipment/status data renders from the live backend |
| Geolocation permission denied | Not live-tested (this sandbox has no real browser to deny permission in) — the code path (`err.code === err.PERMISSION_DENIED`) was reviewed and the message it shows matches the spec exactly, but treat this one as unverified until you test it in a real browser by denying the location prompt. |
| Mobile touch-target sizing for driver buttons | Not tested — no real device/browser available here. The buttons reuse the existing `.btn-primary`/`.btn-secondary` classes sized for touch, but do a real pass on an actual phone before relying on this. |

## API overview

Full interactive docs at `/docs`. Router prefixes: `/auth`, `/vehicles`,
`/drivers`, `/shipments`, `/trips`, `/fuel`, `/maintenance`,
`/assignments`, `/routes`, `/notifications`, `/dashboard`, `/analytics`,
`/reports`.

## Deployment (free tier)

**Database + Backend → Render**
1. Push this repo to GitHub (`.env` is gitignored — no real secrets leak).
2. Render → **New → Blueprint** → point at the repo. It reads
   `render.yaml` and creates a free Postgres database plus the backend
   service automatically.
3. Add a free Redis instance (Render's own, or [Upstash](https://upstash.com)
   free tier) and paste its URL into `REDIS_URL` on the Render service.
4. Leave `GOOGLE_MAPS_API_KEY` unset to keep using the free local
   route estimator, or add your key the same way.
5. Migrations run automatically on deploy (`Dockerfile` CMD).
6. Seed demo data once against the live DB:
   ```bash
   DATABASE_URL="<Render's external connection string>" python seed_demo_data.py
   ```

**Frontend → Vercel / Netlify / GitHub Pages**
1. Deploy the `frontend/` folder as-is — no build command needed.
2. Edit `API_BASE` at the top of `app.js` to your Render backend URL
   before deploying.

**Verify:** `https://<backend>.onrender.com/docs` loads Swagger; your
frontend URL shows the login screen and `admin_demo` / `Demo@1234` works.

## Known limitations

- The frontend is plain JS, not React/Next.js — see Testing/Charts above
  for why, and what it would take to switch. (A later request in this
  same project asked for a "Frontend Dockerfile for React" and to
  document React in the stack — there is no React here, so the Dockerfile
  added instead just serves the static files via nginx, and the stack
  list below only documents what's actually implemented.)
- Notifications are in-app only, not real email/SMS/push.
- Driver accounts are linked to Driver records (`User.driver_id`), but
  this link is set manually by an Admin when creating the account.
- Live location is **real browser Geolocation**, polled to the backend
  every 20s while a trip is in progress — not simulated. It only falls
  back to an elapsed-time route estimate before any real location has
  been reported yet (e.g. trip not started, or location permission
  denied), and the UI always labels which one it's showing.
- The shipment status flow is `Created → Assigned → In Transit →
  Delayed → Delivered/Cancelled` (matching this project's original
  requirements doc) — not the longer `Picked Up → Out for Delivery`
  chain mentioned in one later request. Expanding the enum would mean a
  new migration and touching every status-transition check across the
  app; flagged here rather than done silently, since it's a schema
  decision worth confirming first, not a quick fix.
