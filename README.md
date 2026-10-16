# LMS: lead management SaaS

A multi-tenant lead management app for sales teams. Leads from Meta lead ads, Google Sheets and manual entry
become **Enquiries** linked to unique **Contacts**; the team calls, follows up and moves them to Closed or Lost.
The full product spec is in [LMS_PROJECT.md](LMS_PROJECT.md). **Setup, running and database guide: [SETUP.md](SETUP.md).**

## Features

- **Enquiries and contacts**: one contact per person (duplicates by phone or email are linked), statuses
  (changeable straight from the list), owners, custom fields, notes with voice notes, calls, follow-ups,
  attachments, timeline, Smart Views, saved filters, global search, your own column layout.
- **Meta Lead Ads**: Facebook login popup, every Page (Business Manager Pages too), Auto Sync or form-by-form,
  sync the last 24 hours / 7 / 30 days, new leads within about a minute (webhook on a public server),
  field mapping, and **lead quality feedback** to Meta (Conversions API for CRM) from the LMS statuses.
- **Apps** (header button): connect **WhatsApp Business** (Meta Embedded Signup: new number or the WhatsApp
  Business app number), **Exotel** (numbers, auto-calling) and **Google Sheets** (send a form's leads to a sheet
  and keep it updated, or import a sheet's rows). Google Ads and LinkedIn Ads are coming soon.
- **Exotel auto-calling**: call new leads after 1, 2 or 5 minutes, call at the time of a scheduled call (per call
  on/off), calling hours (days and times), agent rung first then the lead; answered calls mark the follow-up done,
  missed calls show "Call not connected" with Reschedule.
- **Users**: everyone's contact number, alternate phone, email and role; roles Owner, Admin, Manager, Agent, Viewer.
- **Import / export** (CSV, Excel), audit log, notifications, live updates (WebSocket).
- **Installable web app** (PWA) on laptop, phone and tablet.
- **Tenant isolation**: PostgreSQL Row Level Security on every tenant table; MongoDB only through a
  tenant-scoped layer; secrets (Meta, Exotel, Google tokens) encrypted at rest.

## Quick start

```bash
git clone https://github.com/TPT-Projects/LMS-Product.git
```
Then follow [SETUP.md](SETUP.md): PostgreSQL, MongoDB (or `mongomock://` for development), Python venv,
`backend/.env` from `backend/.env.example`, `python manage.py migrate`, `npm install` and `npm run dev`.
Secrets are never committed: `.env` files are ignored by git.

| Layer | Stack |
|---|---|
| Frontend | React 19, TypeScript (strict), Tailwind CSS 4, React Router, TanStack Query + Table, React Hook Form + Zod, Radix UI, i18next |
| Backend | Python, Django 5.2, Django REST Framework, SimpleJWT, Celery, Channels |
| Data | PostgreSQL (Row Level Security) · MongoDB (form data and activity logs only) · Redis |

---

## Backend: `backend/`

```
backend/
├─ manage.py
├─ requirements.txt / requirements-dev.txt
├─ pyproject.toml              ruff, black and pytest config
├─ Dockerfile
├─ .env.example                every setting the app reads
├─ config/                     project wiring
│  ├─ settings/  base.py · dev.py · test.py · prod.py
│  ├─ urls.py                  /api/v1/... and /health/
│  ├─ asgi.py · wsgi.py · celery.py
├─ common/                     shared building blocks (no business logic)
│  ├─ tenancy/
│  │  ├─ context.py            current tenant + Postgres `app.tenant_id`, tenant_context(), rls_bypass()
│  │  ├─ rls.py                EnableRLS migration operation (policy + FORCE RLS)
│  │  ├─ authentication.py     JWT → membership → activates the tenant on every request
│  │  ├─ middleware.py         tenant guard: clears tenant state around each request
│  │  ├─ models.py             TenantScopedModel (adds tenant_id)
│  │  ├─ mixins.py             TenantScopedViewMixin (ORM scoping for views)
│  │  └─ permissions.py        IsTenantMember
│  ├─ mongo.py                 the ONLY MongoDB access layer (always adds tenant_id)
│  ├─ realtime.py · consumers.py  WebSocket /ws/tenant/ (live leads, notifications), tenant-scoped groups
│  ├─ crypto.py                encrypts Meta tokens at rest (FIELD_ENCRYPTION_KEY)
│  ├─ phones.py                phone (E.164 via phonenumbers) and email normalisation
│  ├─ pagination.py            25 / 50 / 100 / 200 page sizes
│  ├─ dates.py                 UTC storage, DD/MM/YYYY display
│  └─ exceptions.py            one error shape for the whole API
├─ apps/
│  ├─ tenants/                 Tenant (workspace) model, /workspace, seed_demo + ensure_mongo_indexes commands
│  ├─ accounts/                User, Membership, Invitation · services.py (business logic)
│  │  ├─ views/auth.py         signup, login, refresh, logout, forgot/reset password, accept-invite, me, switch-workspace
│  │  └─ views/users.py        list members, invite, change role, invitations
│  ├─ permissions/             roles, the permission matrix (spec section 5), DRF permission classes
│  ├─ teams/                   Team, TeamMember, /teams
│  ├─ statuses/                Status (default New/Contacted/Qualified/Closed/Lost), /statuses, reorder
│  ├─ contacts/                Contact (read-only, unique phone/email per workspace), /contacts
│  ├─ enquiries/               the working module
│  │  ├─ ingestion.py          ONE entry point: dedupe → contact → enquiry → timeline (manual, import, Meta)
│  │  ├─ services.py           update (tracked changes), soft delete, notes, calls, follow-ups, attachments, bulk
│  │  ├─ selectors.py          who sees which enquiries (role scopes) + system smart views
│  │  ├─ filters.py            AND/OR JSON filter engine → safe ORM queries, search, sorting
│  │  ├─ views/                enquiries.py (list/detail/bulk/timeline) · work_items.py (notes, calls, …)
│  │  └─ management/commands/  seed_enquiries (realistic sample leads)
│  ├─ customfields/            CustomField + typed EnquiryCustomValue, values.py (typed validation)
│  ├─ views/                   SavedView + per-user pins, /views, /views/counts
│  ├─ search/                  /search (global search)
│  ├─ activity/                service.py: MongoDB activity_logs (timeline), written after commit
│  ├─ audit/                   AuditLog (exports, role changes, invites, Meta connect/disconnect)
│  ├─ notifications/           Notification (bell), /notifications, pushed live over WebSocket
│  ├─ importexport/            readers.py (CSV/Excel) · processing.py (mapping, validation) · services.py
│  │                           (live ≤100 rows / Celery background, failed-row report) · /exports (CSV)
│  ├─ integrations/            Apps: providers.py (WhatsApp, Exotel: fields + live check) · Integration
│  │                           model (encrypted secrets) · services.py (connect, check, overview)
│  └─ meta_integration/        graph.py (Graph API) · services.py (OAuth, one Page, forms, mapping)
│                              leads.py (lead → enquiry pipeline) · tasks.py (webhook jobs, backfill)
│                              formdata.py (MongoDB lead_form_responses) · meta_simulate_lead command
└─ tests/                      auth, roles, RLS + MongoDB + WebSocket isolation, enquiries, filters/views/search,
                               10k-row speed, import/export, Meta (replays docs/reference leads)
```

**Conventions**
- Views are thin: a serializer validates input, then one function in `services.py` does the work.
- Every tenant table extends `TenantScopedModel` **and** gets `EnableRLS("<table>")` in a migration.
- Never import `pymongo` outside `common/mongo.py`. A test enforces this.
- Permissions come from `apps/permissions/matrix.py`. Check them with `require(Capability.X)`.
- Every enquiry query starts from `visible_enquiries(membership)`, so role scopes can't be forgotten.
- Contacts and enquiries are only created through `ingest_enquiry()`, so dedupe rules live in one place.

## Frontend: `frontend/`

```
frontend/src/
├─ main.tsx                    entry point
├─ app/                        App.tsx · providers.tsx (Query + Auth) · router.tsx (all routes, lazy-loaded) · NotFoundPage
├─ routes/                     paths.ts (every URL) · guards.tsx (ProtectedRoute, GuestRoute, RequireCapability)
├─ components/
│  ├─ ui/                      Button, Input, Select, Textarea, Checkbox, DateInput (DD/MM/YYYY), ChipGroup, Tabs,
│  │                           FormField, Card, Badge, Alert, Dialog, DropdownMenu, Avatar, EmptyState, Skeleton, Spinner
│  ├─ data-table/              DataTable (server paging) · Pagination · pageNumbers
│  └─ layout/                  AppShell, Sidebar, Topbar, WorkspaceSwitcher, UserMenu, NotificationBell, AuthLayout, PageHeader
├─ features/                   one folder per business area
│  ├─ auth/                    api.ts · AuthProvider · useAuth · schemas.ts · pages/ (Login, Signup, Forgot, Reset, AcceptInvite)
│  ├─ users/                   api.ts (TanStack Query hooks) · roles.ts · components/ · pages/UsersPage
│  ├─ teams/                   api.ts · components/TeamDialog · pages/TeamsPage
│  ├─ workspace/               api.ts · timezones.ts · components/ · pages/WorkspaceSettingsPage
│  ├─ settings/                SettingsLayout (tabs)
│  ├─ enquiries/               api.ts · filters.ts (builder model) · useEnquiryListParams (state in the URL)
│  │  ├─ pages/                EnquiriesPage (table, views, filters, bulk) · EnquiryDetailPage
│  │  └─ components/           FilterBuilderDialog, QuickFilterMenu, BulkActionBar, EnquiryFormDialog,
│  │                           QuickActions, DetailsCard, CustomFieldsCard, ActivityTimeline,
│  │                           NotesPanel, CallsPanel, FollowUpsPanel, AttachmentsPanel, FormResponseCard
│  ├─ contacts/                api.ts · pages/ContactsPage, ContactDetailPage (read-only)
│  ├─ statuses/                api.ts · colors.ts · StatusBadge · StatusDialog · pages/StatusesSettingsPage
│  ├─ customfields/            api.ts · values.ts · CustomFieldInput · CustomFieldDialog · settings page
│  ├─ views/                   api.ts · SaveViewDialog · pages/ViewsPage (saved views manager)
│  ├─ search/                  GlobalSearch (top bar, "/" shortcut)
│  ├─ imports/                 api.ts · pages/ImportsPage (log), ImportWizardPage, ImportDetailPage
│  ├─ notifications/           api.ts · pages/NotificationsPage (the bell is in components/layout)
│  ├─ live/                    LiveEventsProvider: one WebSocket per tab, "new leads" pill
│  ├─ integrations/            catalog.ts (every app) · api.ts · AppsMenu (top bar), AppCard,
│  │                           ConnectAppDialog, GetStartedChecklist · pages/AppsMarketplacePage, AppDetailPage
│  ├─ meta/                    api.ts · ConnectionCard, PagePicker, ConnectGuide, FormsCard, SyncCard,
│  │                           MetaTokenBanner · pages/MetaSettingsPage, MetaSetupPage (Page → forms →
│  │                           sync leads), MetaOAuthDonePage (popup return), MetaFormMappingPage
│  └─ placeholders/            ComingSoonPage for modules from later phases
├─ hooks/                      usePageParams, useHotkeys, useFieldError, useDebouncedValue
├─ lib/                        api/ (axios client + auto token refresh) · dates · i18n · theme · storage · cn
├─ locales/en.json             every piece of UI text (no hardcoded strings)
├─ types/                      shared API and auth types
└─ styles/index.css            Tailwind + design tokens (light and dark)
```

**Conventions**
- Each feature has its own `api.ts` (requests + query hooks), `components/` and `pages/`.
- All text goes through `t('…')`. A test fails if a key is missing from `en.json`.
- Colors come from tokens (`bg-surface`, `text-fg-muted`, `bg-accent`…) defined once in `styles/index.css`.
- Dates are always shown with `useDateFormat()` (DD/MM/YYYY, workspace timezone).
- The UI hides what a role cannot do, but the API is the real gatekeeper.

## API

All endpoints are under `/api/v1/`. Lists accept `page` and `page_size` (25/50/100/200) and return `count, next, previous, page, page_size, total_pages, results`.

| Endpoint | Who |
|---|---|
| `POST auth/signup` · `auth/login` · `auth/refresh` · `auth/logout` | anyone |
| `POST auth/forgot-password` · `auth/reset-password` | anyone |
| `GET/POST auth/accept-invite` | anyone with the invite token |
| `GET auth/me` · `POST auth/switch-workspace` | logged in |
| `GET/PATCH workspace` | read: members · edit: Owner, Admin |
| `GET/POST users` · `PATCH users/{id}/role` | read: members · invite and roles: Owner, Admin |
| `GET invitations` · `DELETE invitations/{id}` | Owner, Admin |
| `GET/POST/PATCH/DELETE teams[/{id}]` | read: members · edit: Owner, Admin |
| `GET/POST/PATCH statuses[/{id}]` · `POST statuses/reorder` | read: members · edit: Owner, Admin |
| `GET/POST/PATCH custom-fields[/{id}]` | read: members · edit: Owner, Admin |
| `GET contacts` · `GET contacts/{id}` | members (read-only; scoped like enquiries) |
| `GET/POST enquiries` · `GET/PATCH/DELETE enquiries/{id}` | scoped by role; edit: Owner, Admin, Manager, Agent (own) |
| `POST enquiries/bulk` | `set_status`, `assign`, `add_secondary_owner`, `delete` (permission per action) |
| `GET enquiries/{id}/timeline` · `GET enquiries/{id}/form-response` | anyone who can see the enquiry |
| `GET/POST enquiries/{id}/notes` · `calls` · `followups` · `attachments` | see: anyone who can see it · add: edit permission |
| `PATCH enquiries/{id}/followups/{fid}` · `GET …/attachments/{aid}/download` | mark done · private file download |
| `GET/POST/PATCH/DELETE views[/{id}]` · `POST/DELETE views/{id}/pin` · `GET views/counts` | own + shared views |
| `GET search?q=` | global search |
| `GET/PUT preferences/tables/{enquiries\|contacts\|users}` | the user's own column layout |
| `GET …/notes/{nid}/audio` | private voice-note playback |
| `GET/POST imports` · `GET imports/{id}` · `POST imports/{id}/map` · `GET …/preview` · `POST …/run` · `GET …/failed-report` · `GET imports/template` | Owner, Admin, Manager |
| `POST exports` | Owner, Admin, Manager (audited) |
| `GET notifications` · `POST notifications/{id}/read` · `POST notifications/read-all` | own notifications |
| `GET meta/status` · `POST meta/connect` · `GET meta/pages` · `POST meta/page` · `POST meta/check-access` · `DELETE meta/connection` · `PATCH meta/settings` | Owner, Admin |
| `GET meta/forms` · `POST meta/forms/refresh` · `POST meta/forms/{id}/connect\|disconnect` · `GET/PUT meta/forms/{id}/mapping` | Owner, Admin |
| `POST meta/sync {days, restore_deleted?, form?}` · `POST meta/poll` (any member; at most once a minute per workspace) | Owner, Admin · any member |
| `GET/PATCH meta/conversions` (`{enabled, dataset_id, token}`) · `POST meta/conversions/test` | Owner, Admin |
| `GET meta/sync-logs` · `GET meta/failed-syncs` · `POST meta/failed-syncs/{id}/retry` | Owner, Admin |
| `PATCH meta/settings {auto_connect_forms}` · `POST meta/sync {days: 1\|7\|30}` (returns checked, added, errors) | Owner, Admin |
| `GET /api/meta/callback/` (outside `/api/v1`) | Facebook login return; the signed `state` identifies the user, then redirects to `/meta/oauth-done` |
| `GET integrations` · `POST integrations/exotel` (`{values}`, checked with Exotel first) · `POST integrations/{app}/check` · `DELETE integrations/{app}` | Owner, Admin (`manage_integrations`) |
| `GET/PATCH integrations/exotel/manage` · `POST integrations/exotel/refresh` · `POST/DELETE integrations/exotel/numbers[/{id}]` · `GET integrations/exotel/forms` · `PATCH integrations/exotel/forms/{id}` · `GET integrations/exotel/calls` | Owner, Admin |
| `GET integrations/whatsapp/signup-config` · `POST integrations/whatsapp/embedded` (Embedded Signup) · `POST integrations/whatsapp/numbers/{id}/register` · `POST integrations/whatsapp/connect` · `GET/PATCH integrations/whatsapp/manage` · `POST integrations/whatsapp/refresh` | Owner, Admin |
| `POST integrations/google_sheets/connect` · `GET …/spreadsheets` · `GET …/spreadsheets/{id}/tabs` · `GET/POST …/links` · `POST …/exports` (send a form's leads to a sheet) · `PATCH/DELETE …/links/{id}` · `POST …/links/{id}/sync` | Owner, Admin |
| `GET integrations/calling` (is auto-calling of scheduled calls on?) · `PATCH enquiries/{id}/followups/{fid}` `{done, auto_call, due_at (reschedule)}` | any member |
| `POST integrations/heartbeat` (due auto-calls, new leads, sheet rows, daily number refresh) | any member |
| `PATCH users/{id}/profile` (`{full_name, phone, alternate_phone}`) | self, or Owner/Admin |
| `GET /api/integrations/google/callback/` · `POST /webhooks/exotel/{signed token}` (outside `/api/v1`) | Google login return · Exotel call results |
| `GET/POST /webhooks/meta` (outside `/api/v1`) | Meta only: verify token + `X-Hub-Signature-256` |
| WebSocket `/ws/tenant/?token=<access>` | live `enquiry.created` and `notification` events |

**Enquiry list parameters:** `view` (all, mine, unassigned, calls-today), `saved_view`, `q`, `status`, `owner` (ids or `me`), `source`,
`campaign`, `form`, `created_from` / `created_to` (DD/MM/YYYY), `filter` (JSON AND/OR tree), `sort`, `page`, `page_size`.

```json
{"op": "or", "rules": [
  {"op": "and", "rules": [
    {"field": "campaign", "operator": "contains", "value": "Dubai"},
    {"field": "cf:investment_budget", "operator": "in", "value": ["₹5_cr+"]}
  ]},
  {"field": "created_at", "operator": "last_days", "value": 7}
]}
```
"# LMS-Product" 
