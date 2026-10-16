# LMS: setup and run guide (start to end)

This guide takes you from an empty machine to a running app. The commands are written for **Windows** (PowerShell or Git Bash). macOS and Linux use the same commands, except where a step says otherwise.

> **The short version** (once everything is installed):
> ```bash
> docker compose up -d                                         # databases
> cd backend && .venv\Scripts\activate && python manage.py runserver   # API  → http://localhost:8000
> cd frontend && npm run dev                                   # web  → http://localhost:5173
> ```

---

## 1. What you need to install

| Tool | Version | Why | Check |
|---|---|---|---|
| Git | any | version control | `git --version` |
| Python | **3.13** (3.12–3.14 work) | Django backend | `python --version` |
| Node.js | **22 LTS** or newer | React frontend | `node -v` |
| Docker Desktop | latest | runs PostgreSQL, MongoDB, Redis | `docker ps` |

- Python: https://www.python.org/downloads/ (tick **"Add python.exe to PATH"**)
- Node.js: https://nodejs.org/ (LTS)
- Docker Desktop: https://www.docker.com/products/docker-desktop/ (on Windows it needs **WSL 2**; the installer offers to set it up)

> **Docker will not start?** Open Docker Desktop and read its error. On Windows the usual fixes are: run `wsl --update` in an admin PowerShell, make sure virtualization is enabled in the BIOS, then restart. If you cannot use Docker, see [section 9](#9-running-without-docker).

---

## 2. Project layout

```
LMS/
├─ LMS_PROJECT.md          ← the product spec (single source of truth)
├─ SETUP.md                ← this file
├─ README.md               ← overview and folder structure
├─ docker-compose.yml      ← PostgreSQL, MongoDB, Redis (+ optional app containers)
├─ docker/postgres/        ← creates the non-superuser app role on first start
├─ docs/reference/         ← sample Meta lead JSON files, UI screenshots
├─ .github/workflows/ci.yml← lint, type-check and tests on every push
├─ backend/                ← Django + Django REST Framework API
└─ frontend/               ← React + TypeScript + Tailwind web app
```

See [README.md](README.md) for what is inside `backend/` and `frontend/`.

---

## 3. Start the databases (Docker)

From the project root:

```bash
docker compose up -d
docker compose ps
```

All three services should be `healthy` after a few seconds:

| Service | Address on your machine | Used for |
|---|---|---|
| PostgreSQL 16 | `localhost:5433` | all structured data (with Row Level Security) |
| MongoDB 7 | `localhost:27017` | Meta form responses and activity logs |
| Redis 7 | `localhost:6379` | Celery queues and live updates (later phases) |

**Why port 5433?** Many Windows machines already run a local PostgreSQL on 5432. To keep the two apart, the Docker one is published on **5433**. If you want a different port, set `POSTGRES_HOST_PORT` in a root `.env` file and change `POSTGRES_PORT` in `backend/.env` to match.

**How the database user works:** on first start, `docker/postgres/01-create-app-role.sh` creates the database `lms` and a user `lms_app`. That user is deliberately **not** a superuser, because superusers skip Row Level Security, the rule that keeps each workspace's data apart.

Useful commands:

```bash
docker compose logs -f postgres     # watch logs
docker compose stop                 # stop (data is kept)
docker compose down -v              # stop AND delete all data (fresh start)
```

---

## 4. Set up the backend (Django)

```bash
cd backend

# 1. Create a virtual environment (once)
python -m venv .venv

# 2. Activate it (every new terminal)
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
#   PowerShell says "running scripts is disabled"? Skip activating and run
#   every python command as  .venv\Scripts\python manage.py ...  instead.

# 3. Install packages
pip install -r requirements-dev.txt

# 4. Create your settings file
copy .env.example .env            # PowerShell or cmd (use cp in Git Bash, macOS, Linux)
```

Open `backend/.env` and set at least:

```ini
DJANGO_SECRET_KEY=<a long random string>
```

Generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

The database values in `.env.example` already match `docker-compose.yml`.

```bash
# 5. Create the tables (and the Row Level Security policies)
python manage.py migrate

# 6. Create the MongoDB indexes
python manage.py ensure_mongo_indexes

# 7. (Optional) Demo workspace with one user per role
python manage.py seed_demo
#   prints the logins: owner@demo.test, admin@demo.test, manager@demo.test, agent@demo.test, viewer@demo.test
#   and the password. Use --password <yours> to choose one.

# 8. (Optional) 60 realistic sample enquiries in the demo workspace
python manage.py seed_enquiries
#   --count 200, or --workspace "<name or id>" for another workspace

# 9. (Optional) Simulate a Meta lead from the reference files (no Meta app needed)
python manage.py meta_simulate_lead ../docs/reference/sample_2_Leads_Event4th5thJuly_10_06_26.json --new-id

# 10. Run the API (Daphne: HTTP and the live-update WebSocket)
python manage.py runserver
```

Check it: open http://localhost:8000/health/. It should show `{"status": "ok"}`.

> **Redis is optional in development.** With `REDIS_URL=` empty, background imports run inline and
> live updates work inside the one server process. With Redis, also start a worker and the scheduler
> in two more terminals (on Windows add `--pool=solo` to the worker):
> ```bash
> celery -A config worker -l info --pool=solo
> ```
> ```bash
> celery -A config beat -l info
> ```
> Beat runs the Meta backfill every 15 minutes.

> **Emails in development:** with `EMAIL_HOST` empty, invite and password-reset emails are **printed in the API terminal**. Copy the link from there. The invite dialog in the app also shows the link.

---

## 5. Set up the frontend (React)

In a **second terminal**:

```bash
cd frontend
npm install
copy .env.example .env            # PowerShell or cmd (use cp in Git Bash, macOS, Linux)
npm run dev
```

> **PowerShell says "npm.ps1 cannot be loaded"?** Use `npm.cmd` instead of `npm`
> (for example `npm.cmd run dev`). It does the same thing.

Open http://localhost:5173.

`frontend/.env` holds:

```ini
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

---

## 6. Try it

**Phase 0: workspaces, users and roles**

1. Go to http://localhost:5173/signup and create a workspace. You become its **Owner**.
2. Go to **Settings → Users & roles → Invite user**, enter an email and pick a role (for example Manager).
3. Copy the invite link from the dialog (or from the API terminal), open it in a private window, set a name and password, and click **Join workspace**.
4. You are now logged in as that user, with that role. Owner-only controls are hidden, and the API refuses them too.
5. Sign up a second workspace. Neither workspace can see the other's data. The automated tests prove this for PostgreSQL and MongoDB (step 7).

**Phase 1: contacts and enquiries**

1. Press **Q** (or the **+** button) and create an enquiry with a phone number. A Contact is created automatically.
2. Create another enquiry with the same phone typed differently (for example `98765 43210` instead of `+919876543210`). It is linked to the same Contact and marked **Repeat enquiry**.
3. Open the enquiry: change the status from the badge, use **Call / WhatsApp / Email / Add note**, log a call, schedule a follow-up (DD/MM/YYYY), attach a file. Everything appears on the **Timeline**.
4. **Contacts** is read-only and lists every enquiry of a person.

**Phase 2: find enquiries fast**

1. **Settings → Custom fields**: add fields such as *Investment budget* (dropdown) or *City* (text).
2. On **Enquiries**, use the search box, the Status / Owner / Source chips, or **Filters** to build AND/OR rules (including custom fields).
3. Click **Save view**, tick *Share with the workspace*, and the view appears in the sidebar with a live count.
4. Select rows to change status, assign or delete in bulk. Use **/** to jump to global search (name, any phone format, email, campaign, form, custom text).

**Your own columns, the Action badge and voice notes**

1. On **Enquiries** (also Contacts and Users) click **Columns**: tick the columns you want and drag them (or use the arrows) into your order. On Enquiries and Contacts, **Name, Action and Status are always the first three columns**. Enquiries show Owner, Source, Campaign and Created by default; custom fields and the rest can be ticked in. The layout is saved to your account; **Reset to default** brings back the default columns.
2. The **Action** column shows the next step: red *Overdue*, amber *Today 10:00*, blue *Call 16/10*, or *Schedule call*. Click it to schedule a call, log a call, add a note, mark the follow-up done, or call / WhatsApp / email.
3. In **Add note**, press **Voice note**, allow the microphone, speak, press **Stop**, then **Add note**. Voice notes play back on the enquiry (up to 10 minutes each).

**Phase 3: import and export**

1. **Imports → New import**: drop a CSV or Excel file (or download the template first).
2. Check how the columns were matched, then **Preview**: you see valid rows, rows with problems, and matches with existing contacts. Nothing is saved yet.
3. **Import**: up to 100 rows import at once; bigger files run in the background and the bell shows a notification when done.
4. Open the import to see new / linked / failed counts, and **Download failed rows** to fix and re-import them.
5. On **Enquiries**, **Export** downloads the current list (filters, saved view and your columns) as a CSV that opens correctly in Excel. Every export is written to the audit log.

**Apps (Meta, WhatsApp, Exotel, Google Sheets)**

Owners and Admins see an **Apps** button in the top bar (and **Apps** in the sidebar). Available: **Meta Lead
Ads**, **WhatsApp Business**, **Exotel**, **Google Sheets**. Coming soon: Google Ads, LinkedIn Ads.

*Users and phone numbers.* **Users** in the sidebar lists everyone with username, contact number, email,
alternate phone and role. Owners/Admins edit anyone; others edit themselves. **Add every agent's contact
number**: Exotel rings it first for their auto-calls.

*WhatsApp (guided signup, like Make.com).* On Apps › WhatsApp choose **Connect a number** (a new number, or one
already on the WhatsApp Business Platform; verified by SMS or call in the popup) or **Connect the app number**
(keep using your WhatsApp Business app on the phone: "coexistence"). Facebook's Embedded Signup popup guides you;
afterwards the LMS subscribes to the account, registers new numbers (the two-step PIN is shown on the Manage
page) and lists the numbers so you can choose the one your team uses. One-time setup in the Meta app:
1. Add the use case **"Connect with customers through WhatsApp"**.
2. **Facebook Login for Business › Configurations › Create configuration**, choose the **WhatsApp Embedded
   Signup** variation, and put its ID in `backend/.env` as `META_WHATSAPP_CONFIG_ID`.
3. **Facebook Login for Business › Settings**: turn on **Login with the JavaScript SDK** and add `localhost`
   (and your domain later) to **Allowed domains for the JavaScript SDK**.
Without `META_WHATSAPP_CONFIG_ID` the page offers a plain Facebook login that connects an existing WhatsApp
Business Account. For other companies to use the guided signup in production, Meta requires the app to be a
Tech Provider (App Review).

*Exotel.* Click **Connect**, choose the region and paste the Account SID, API key and API token
(Exotel › Settings › API Settings). The Manage page then shows:
- **Your numbers**: every active ExoPhone with *Active since* (shown in your workspace time zone; hover for
  UTC), voice/SMS, **Make default** (the caller ID for auto-calls), **Refresh**, and **Add number** for a
  number Exotel does not list yet. Numbers also refresh automatically once a day.
- **Auto-calling**: call at the time of a scheduled call, and who gets calls for unassigned leads. When this is
  on, the schedule-call form on an enquiry shows "This call will be auto-called with Exotel" with a switch, so
  it can be turned off for that enquiry's call (and each scheduled call has its own Auto-call switch).
- **New lead calling**: call new leads after **1, 2 or 5 minutes** (default 2) and the connected Meta forms with an
  on/off switch each; a new lead from a form that is on is called after that delay.
- **Recent auto-calls**: scheduled, placed and skipped calls, with the reason.

- **Calling hours**: days and from/until times (workspace time zone) for every form and scheduled call. New-lead
  calls outside them wait for the next opening; a call that will be auto-called can only be scheduled inside them.

After a call: if the lead answered (Exotel reports talk time), the call is logged and the scheduled call is
**marked done** automatically. If not, it is logged and the scheduled call shows **Call not connected** with
**Reschedule** (on the enquiry and on the list's Action badge); the new time is auto-called again. On localhost
the LMS asks Exotel for the result about a minute after the call (no public URL needed).

When you schedule a call, it is assigned to the **lead's owner** by default; anyone can pick another person.

How a call works: Exotel rings the agent's phone first (the lead's owner, the person the call was scheduled
for, or the fallback person), then connects the lead, showing the default ExoPhone. Calls are placed by the
heartbeat (about every minute while anyone has the LMS open) or by Celery Beat in production. A call more than
15 minutes late is skipped. On a public HTTPS server Exotel also reports the result, which is logged on the
enquiry (Calls tab).

*Lead quality feedback (Meta Conversions API).* Settings › Meta › **Lead quality feedback**: enter the CRM
**dataset ID** and a **Conversions API access token** (Meta Events Manager › your dataset › Settings), then turn it
on. Every Meta lead's status (when it arrives and each time it changes) is sent to Meta as a lead stage with the
lead ID; in Events Manager map your statuses to Meta's stages (e.g. New = Lead, Qualified = Qualified lead,
Closed = Converted). Use a test event code from Events Manager › Test events to check the setup. Only Meta
leads are sent.

*Change status from the list.* On Enquiries, click a lead's status badge to change it without opening the lead.

*Install as an app.* In Chrome or Edge (laptop, Android phone or tablet) use the account menu › **Install app**
(or the install icon in the address bar). On iPhone/iPad open the LMS in Safari › Share › **Add to Home Screen**.
The app opens in its own window. Installing needs `localhost` or HTTPS.

*Google Sheets.* One-time setup in Google Cloud (console.cloud.google.com): create a project, enable the
**Google Drive API** and **Google Sheets API**, configure the OAuth consent screen (add yourself as a test
user while testing), then create an **OAuth client ID** (Web application) with the authorised redirect URI
`http://localhost:8000/api/integrations/google/callback/`. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
in `backend/.env` and restart the API. Then in Apps › Google Sheets click **Connect with Google**. Two things
you can do:
- **Send leads to a sheet** (forms are listed with their lead counts; a switched-off form is switched on so its
  leads arrive; a sheet's form can be changed later): choose a Meta form (e.g. your real estate form) or all enquiries, and a new
  spreadsheet or a new tab in one of yours. All its leads are written there, and new leads, status, owner and
  other changes update the sheet about every minute (**Sync now** writes at once). Edits made in the sheet are
  not copied back into the LMS.
- **Import a sheet**: pick a spreadsheet and tab, check the name / phone / email columns; rows become enquiries
  and new rows are picked up every 5 minutes.
If you connected Google before this version, use **Log in again** once so the LMS may write to sheets.

**Phase 4: Meta lead ads**

1. Create an app at developers.facebook.com, add *Facebook Login* and *Webhooks*, and put `META_APP_ID`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN` (any secret text) and `FIELD_ENCRYPTION_KEY` in `backend/.env`.
2. In the Meta app, under **Facebook Login → Settings → Valid OAuth Redirect URIs**, add exactly
   `http://localhost:8000/api/meta/callback/` (in production: `https://<your API>/api/meta/callback/`; it is
   `BACKEND_URL` + `/api/meta/callback/`, or whatever you set in `META_OAUTH_REDIRECT_URI`). **Settings → Meta** also
   shows the *Webhook URL* (must be public HTTPS; use a tunnel such as ngrok while testing).
3. Click **Connect Meta**. Facebook login opens in a **popup**. After you log in, the popup closes and the LMS
   shows the setup in three steps:
   1. **Page**: every Page you allowed in the popup is listed (also Pages you manage through a Business
      Manager); pick one. In the popup choose **Opt in to all current and future Pages** to see them all here.
      Missing a Page later? Click **Log in again** on this step.
   2. **Forms**: only the forms of that Page, with a search box. **Auto Sync all forms** is on by default
      (every form, including forms created later, syncs). Turn it off to switch forms on or off one by one;
      the list keeps its order (A-Z) when you switch a form on.
   3. **Sync leads**: choose **Last 24 hours**, **Last 7 days** or **Last 30 days** and click **Sync leads**.
      Leads already in the LMS are skipped. **Finish** opens Enquiries with the synced leads.

   Leads also sync **on their own**:
   - Right after you pick the Page (and whenever Auto Sync is turned on or a form is switched on), the last
     30 days are brought in automatically. Enquiries you deleted in the LMS stay deleted; only the
     **Sync leads** button brings them back.
   - While the LMS is open, it checks Meta for new leads about **every minute** (every 5 minutes in a background
     tab). New leads appear in Enquiries by themselves. This needs no public URL, so it works on `localhost`.
   - On a server with a public **HTTPS** address (`BACKEND_URL=https://…`), connecting a Page also registers
     Meta's webhook automatically, so leads arrive within seconds.

   If the browser blocks popups, the whole tab goes to Facebook and comes back to the setup. Later, the Meta card
   has **Sync leads**, **Setup** and **Log out** (new leads stop; enquiries already created stay). To use another
   Facebook account, log out here and on facebook.com, then click **Connect Meta** again.
4. Grant **Leads Access** in Business Suite → **Check again**. Then **Map fields** on each form in **Manage Forms**
   (several questions may feed one custom field).
5. Send a test lead with Meta's *Lead Ads Testing Tool*. It appears in the list within seconds (a "new lead" pill shows live). **Sync history** and **Failed syncs** (with Retry) are under the forms.
6. No Meta app yet? Run `meta_simulate_lead` (step 9 of section 4) to push the reference leads through the same pipeline.

---

## 7. Run the checks

Backend (inside `backend/`, venv active, databases running):

```bash
pytest              # all tests, including the tenant-isolation suite
ruff check .        # lint
black --check .     # formatting   (use `black .` to fix)
```

Frontend (inside `frontend/`):

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

The same checks run in GitHub Actions on every push (`.github/workflows/ci.yml`).

---

## 8. Run everything in Docker (optional)

Instead of steps 4–5 you can run the API, a Celery worker, Celery beat and the web app in containers:

```bash
copy backend\.env.example backend\.env      # then set DJANGO_SECRET_KEY
docker compose --profile app up -d --build
docker compose exec api python manage.py ensure_mongo_indexes
docker compose exec api python manage.py seed_demo
docker compose exec api python manage.py seed_enquiries
```

The web app is at http://localhost:5173 and the API at http://localhost:8000. Migrations run automatically when the `api` container starts.

---

## 9. Running without Docker

You can install the databases directly instead:

- **PostgreSQL:** install PostgreSQL 16+ and open `psql` as the `postgres` user:
  ```sql
  CREATE ROLE lms_app LOGIN PASSWORD 'lms_app_password' CREATEDB NOSUPERUSER NOBYPASSRLS;
  CREATE DATABASE lms OWNER lms_app ENCODING 'UTF8';
  ```
  Then set `POSTGRES_PORT=5432` (or your port) in `backend/.env`.
  The migrations create the `pg_trgm` extension (fast search). It is a trusted extension,
  so the database owner (`lms_app`) can create it on PostgreSQL 13 or newer.
- **MongoDB:** install MongoDB Community Server, or use a free MongoDB Atlas cluster, and set `MONGO_URI`.
  For a quick try without MongoDB, `MONGO_URI=mongomock://` uses an in-memory fake (development and tests only).
- **Redis:** optional for development (leave `REDIS_URL=` empty). Needed in production for background jobs and
  live updates across servers. On Windows use Memurai or WSL.

---

## 10. Common problems

| Problem | Fix |
|---|---|
| `password authentication failed for user "lms_app"` | You are hitting a different PostgreSQL (often a local install on 5432). Check `POSTGRES_PORT=5433` in `backend/.env`. |
| `role "lms_app" does not exist` after changing `.env` | The init script only runs on the first start. Run `docker compose down -v` and then `docker compose up -d`. **This deletes local data.** |
| RLS tests fail with "rolsuper" | The app is connecting as a superuser. Use `lms_app`, never `postgres`. |
| Frontend shows "Cannot reach the server" | The API is not running, or `VITE_API_BASE_URL` is wrong. Restart `npm run dev` after editing `.env`. |
| CORS error in the browser console | Add your frontend URL to `CORS_ALLOWED_ORIGINS` in `backend/.env`. |
| A value in `.env` contains `# …` text | django-environ does not strip comments that follow a value. Put comments on their own line. |
| `ServerSelectionTimeoutError` (MongoDB) | MongoDB is not running. Run `docker compose ps`. |
| `No module named 'celery'` (or `django`) | You ran the global Python. Use `.venv\Scripts\python manage.py …` or activate the venv first. |
| `permission denied to create extension "pg_trgm"` | Your PostgreSQL is older than 13, or `lms_app` does not own the database. Run `CREATE EXTENSION pg_trgm;` once as `postgres`, then `migrate` again. |
| Timeline is empty after restarting the API | You are using `MONGO_URI=mongomock://` (in-memory). Use a real MongoDB to keep the timeline. |
| Facebook login says "URL blocked" / "redirect_uri is not whitelisted" | The *Valid OAuth Redirect URI* in the Meta app must match `META_OAUTH_REDIRECT_URI` exactly, trailing `/` included. Restart the API after changing `.env`. |
| Meta: "No Pages came back" or a Page's forms are empty | In the Facebook popup allow the Page (or choose *all current and future Pages*) and keep every permission ticked, including *Manage ads* (`pages_manage_ads`, needed to list Instant Forms) and *Business management* (`business_management`, lists Pages owned through a Business Manager). Pages are found from your own Page roles, your ad accounts and your businesses. Use **Log in again** on the Page step. |
| Meta popup shows "This login link expired" | The login took more than 15 minutes or was started from another tab. Click **Connect Meta** again. |
| `Set FIELD_ENCRYPTION_KEY to store Meta tokens` | Generate one: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and put it in `backend/.env`. Keep it safe: changing it makes stored Meta tokens unreadable. |
| Big import hangs on "Queued" | `REDIS_URL` is set but no Celery worker is running. Start the worker, or empty `REDIS_URL` in development. |
| Voice note: "Microphone access was blocked" | Allow the microphone for the site in the browser (lock icon in the address bar). Recording needs `localhost` or HTTPS. |
| New columns, imports or Meta pages give errors after updating | Run `pip install -r requirements-dev.txt`, `npm install` and `python manage.py migrate`, then restart both servers. |

---

## 11. Building the next phases

The spec builds the app in phases (section 12 of `LMS_PROJECT.md`). **Phases 0 to 4 are done.**
Next come Phase 5 (Reports, Dashboard, @mentions) and Phase 6 (hardening and SaaS readiness). To continue, tell Claude:

> Phases 3 and 4 are approved. Build Phases 5 and 6. Run all earlier tests too.

After pulling new code, always run `pip install -r requirements-dev.txt`, `npm install` and
`python manage.py migrate` before starting the servers.

Before Phase 4 (Meta), add `all_fields_analysis.json` to `docs/reference/`, and start Meta App Review early (spec section 13).
