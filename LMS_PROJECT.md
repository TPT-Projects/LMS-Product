# LMS_PROJECT_SPEC.md

> **The LMS Project** is a lead management SaaS. It captures leads in real time from Meta Instant Forms, turns every submission into an **Enquiry** linked to a unique **Contact**, and lets teams manage status, follow-ups, calls, notes and reports.
>
> This file is the single source of truth for building the app. Read all of it before writing code.

---

## 0. How to use this file (instructions for Claude)

1. Put this file in the repo root as `LMS_PROJECT_SPEC.md`. Put the three reference JSON files in `docs/reference/` (see section 4).
2. **Build one phase at a time** (section 12). Start with Phase 0. Do not start the next phase until the current phase's "Done when" checks pass and the owner says to continue.
3. At the start of each phase: restate the phase goal, list the files you will create, then build.
4. At the end of each phase: run the tests, list what was built, list anything skipped, and say how to run the app.
5. Do not add features that are not in this file. If something is unclear, use the default in section 14 and mention it.
6. Never hardcode secrets. Use environment variables (section 15).
7. Every table and every MongoDB document has `tenant_id`. Every query is tenant-scoped. This is the most important rule in the project.
8. Dates are shown as **DD/MM/YYYY** everywhere in the UI, exports and imports. Store UTC, show in the workspace timezone.

---

## 1. Product summary

| Item | Value |
|---|---|
| Type | Multi-tenant SaaS web app |
| Main users | Sales teams that run Meta (Facebook / Instagram) lead ads |
| Core idea | Meta lead arrives, system creates or reuses a Contact, creates an Enquiry, team works it to Closed or Lost |
| Main modules | Contacts (read-only master), Enquiries (working module), Meta integration, Views and filters, Import / Export, Reports and dashboard |
| Region | India first (default country +91, workspace timezone, DPDP compliance) |
| Languages | English UI at launch, but built translation-ready (no hardcoded text), UTF-8 everywhere |

### Key concepts

- **Tenant (workspace):** one business account. All data belongs to a tenant.
- **Contact:** a unique person per tenant, matched by the tenant's dedupe key (phone by default, email optional). Contacts are **read-only for users**. Only the system creates or updates them when an enquiry arrives.
- **Enquiry:** one submission or request from a Contact. A repeat person gets a new Enquiry on the same Contact, marked as **Repeat Enquiry**. This is the module the team works in.
- **Form response:** the raw Meta lead data (varying fields per form). Stored in MongoDB.
- **Activity log:** the timeline of everything that happened to an enquiry. Stored in MongoDB.

---

## 2. Tech stack (fixed, do not change)

| Layer | Technology | Used for |
|---|---|---|
| Frontend | React JS + TypeScript + Tailwind CSS | Web app |
| Backend | Python Django + Django REST Framework | API, auth, permissions, business rules, Meta webhook endpoint |
| Queues and schedules | Celery + Redis (Celery Beat for schedules) | Webhook jobs, bulk imports, scheduled backfill, retries |
| Live updates | Django Channels (WebSocket) | Live new-lead alert in the list, in-app notifications |
| RDBMS | PostgreSQL with `tenant_id` on every table and Row Level Security | All structured data |
| MongoDB | MongoDB with `tenant_id` on every document | **Only** Meta form data and activity logs |
| Files | S3-compatible storage | Attachments, import files, failed-record reports |
| Monitoring | Sentry | Errors |
| Dev | Docker Compose (PostgreSQL, MongoDB, Redis), CI pipeline | Local setup and checks |

Suggested libraries (use unless there is a good reason not to): `djangorestframework`, `djangorestframework-simplejwt`, `django-cors-headers`, `psycopg`, `pymongo`, `celery`, `channels`, `channels-redis`, `django-filter`, `phonenumbers`, `argon2-cffi`, `boto3`, `openpyxl`, `pandas` (import only), `requests`. Frontend: React Router, TanStack Query, TanStack Table, React Hook Form + Zod, a small headless UI kit (for example Radix UI) with Tailwind.

### Repo layout

```
lms/
  LMS_PROJECT_SPEC.md
  docker-compose.yml
  docs/reference/                  # the 3 reference JSON files + UI screenshots
  web/                             # React + TypeScript + Tailwind
    src/
      app/ components/ features/ lib/ routes/ styles/
  api/                             # Django project
    config/                        # settings, urls, asgi, celery
    apps/
      tenants/ accounts/ permissions/ teams/
      contacts/ enquiries/ statuses/ customfields/
      views/ search/ importexport/
      meta_integration/            # oauth, webhook, forms, mappings, sync
      activity/                    # MongoDB activity_logs
      formdata/                    # MongoDB lead_form_responses
      reports/ notifications/ audit/ billing/
    common/                        # tenant middleware, mongo data layer, pagination, dates
```

---

## 3. Data storage rules (RDBMS vs MongoDB)

### Why MongoDB for form data and activity logs

Meta lead form data is **unstructured**: every form has different questions, the questions change over time, and the same idea is worded differently in different forms. In the reference sample (114 leads, 5 forms) there are **15 different form fields**, and several fields exist in only one form. Activity log entries also differ per event type (a call log, a status change and an import event carry different details) and the log is append-only and grows fast. Both fit a document database better than fixed relational columns.

Everything else is structured and relational (users, roles, contacts, enquiries, statuses, follow-ups, mappings) and needs joins, filters and reports, so it stays in PostgreSQL.

### What goes where

| Store | Holds |
|---|---|
| **MongoDB `lead_form_responses`** | The Meta lead exactly as received, plus tenant and link fields |
| **MongoDB `activity_logs`** | Every timeline event for contacts and enquiries |
| **PostgreSQL** | Everything else: tenants, users, roles, teams, memberships; contacts; enquiries with their mapped values; statuses and status history; custom field definitions and values; notes; follow-ups; call logs; attachment records; saved views; the Meta connection, forms and field mappings; import jobs and logs; failed sync logs; notifications; audit log; plans and billing |

### Rules that keep both databases safe and consistent

1. **MongoDB has no Row Level Security.** All MongoDB access goes through one data layer (`common/mongo.py`) that always adds `tenant_id` to every filter and every insert. No view or service may call `pymongo` directly. Tests must prove tenant isolation for MongoDB too.
2. **No transaction across the two databases.** Ingestion order: (1) save the raw lead to MongoDB (unique index on `tenant_id + leadgen_id` makes a repeat safe), (2) create the Contact and Enquiry in **one PostgreSQL transaction** that stores `leadgen_id` on the Enquiry (unique per tenant), (3) write the activity log entry, (4) update the Mongo document with `enquiry_id`. If any step fails, Celery retries and nothing is duplicated.
3. **Reports, filters, smart views and search read only from PostgreSQL.** At ingestion the mapped answers are copied into the Enquiry (standard fields and custom field values). The raw MongoDB data is shown on the enquiry as the "Original form response".
4. **Question names are stored as values, not keys**: `field_data` is a list of `{ "name": ..., "values": [...] }`. Names such as `will_you_attend_the_event?` are therefore safe.
5. **Store answers exactly as received** (for example `yes,_5th_july`, `₹1.9_cr_–_₹3_cr`). For display, replace underscores with spaces. Never edit the stored value.
6. **Status history** stays in PostgreSQL (the conversion report needs it). The same change is also written to `activity_logs` for the timeline.
7. **Audit log** (exports, permission changes, Meta connect / disconnect) stays in PostgreSQL.

### MongoDB collections

**`lead_form_responses`**

```json
{
  "_id": "ObjectId",
  "tenant_id": 12,
  "page_id": "<connected Meta Page id>",
  "leadgen_id": "1690200115622509",
  "form_id": "1623165265438269",
  "created_time": "2026-06-29T17:58:13+0000",
  "campaign_name": "Leads_Event4th5thJuly_10/06/26",
  "adset_name": "Ahmedabad+Gnagar",
  "ad_name": "New Leads ad - Copy 2",
  "field_data": [
    { "name": "full_name", "values": ["Aarav Shah"] },
    { "name": "phone_number", "values": ["+919800022222"] },
    { "name": "email", "values": ["aarav.shah@example.com"] },
    { "name": "will_you_attend_the_event?", "values": ["yes,_5th_july"] },
    { "name": "what_is_your_primary_goal?", "values": ["investment"] }
  ],
  "status": "synced",
  "unmapped_questions": [],
  "enquiry_id": 8841,
  "received_at": "2026-06-29T17:58:15Z",
  "raw_event": { }
}
```

- `status` values: `received`, `form_not_connected`, `synced`, `failed`.
- `unmapped_questions`: question names with no mapping yet.
- Indexes: unique `(tenant_id, leadgen_id)`; `(tenant_id, form_id, created_time)`; `(tenant_id, enquiry_id)`.

**`activity_logs`** (append-only, never updated or deleted by users)

```json
{
  "_id": "ObjectId",
  "tenant_id": 12,
  "enquiry_id": 8841,
  "contact_id": 3320,
  "type": "status_changed",
  "actor": { "type": "user", "id": 45, "name": "Riya Shah" },
  "created_at": "2026-06-30T09:12:00Z",
  "details": { "from": "New", "to": "Contacted" }
}
```

- `type` values: `enquiry_created`, `repeat_enquiry`, `contact_information_updated`, `status_changed`, `field_changed`, `assignment_changed`, `note_added`, `call_logged`, `followup_scheduled`, `followup_completed`, `attachment_added`, `mention`, `import_created`, `meta_sync_failed`. `actor.type` is `user` or `system`.
- Indexes: `(tenant_id, enquiry_id, created_at desc)`; `(tenant_id, contact_id, created_at desc)`; `(tenant_id, type, created_at)`.

### PostgreSQL core tables (names are a guide; keep `tenant_id` on all)

| Area | Tables (key columns) |
|---|---|
| Tenancy and users | `tenants` (name, timezone, dedupe_key = phone/email, default_country, plan), `users`, `memberships` (user, tenant, role), `teams`, `team_members` |
| Contacts | `contacts` (tenant, phone_e164, email_lower, name, created_at, deleted_at) with unique partial indexes on `(tenant_id, phone_e164)` and `(tenant_id, email_lower)` where not null |
| Enquiries | `enquiries` (tenant, contact, leadgen_id unique per tenant nullable, source, campaign_name, adset_name, ad_name, form_id, status, primary_owner, is_repeat, mapped name/phone/email as submitted, created_at, deleted_at), `enquiry_owners` (secondary owners), `enquiry_custom_values` |
| Statuses | `statuses` (name, order, is_default, is_closed), `status_history` |
| Custom fields | `custom_fields` (key, label, type: text/number/dropdown/date/currency/etc., options, enquiries only) |
| Work items | `notes`, `followups` (due_at, assignee, done_at), `call_logs` (duration, outcome, notes, provider nullable), `attachments` (file key, size, type) |
| Views | `saved_views` (filter JSON, owner, shared, pinned, name) |
| Meta | `meta_connections` (one per tenant, unique on tenant; unique on page_id across all tenants; encrypted token, expiry), `meta_forms` (form_id, name, status_on_meta, is_connected), `form_field_mappings` (form_id, question_name, target_type: name/phone/email/custom, custom_field), `sync_logs`, `failed_sync_logs` |
| Import | `import_jobs` (file, row_count, mode live/background, status, counts), `import_rows_failed` |
| Other | `notifications`, `audit_log`, `assignment_rules` (priority, condition campaign/form, strategy), `plans`, `usage` |

---

## 4. Reference data (real Meta lead JSON)

Put these three files in `docs/reference/`. They show the real shape of the data the app will receive. **Design the ingestion, mapping UI and tests against them.**

| File | What it is |
|---|---|
| `all_fields_analysis.json` | Analysis of 114 Meta leads: 15 unique fields across 5 campaigns / forms, with counts and sample values |
| `sample_1_Leads_Dubai_Properties_09_06_26.json` | One lead from the Dubai Properties form |
| `sample_2_Leads_Event4th5thJuly_10_06_26.json` | One lead from the Event 4th-5th July form |

### Sample lead 1: Dubai Properties form

```json
{
  "id": "1332954398230203",
  "created_time": "2026-06-11T20:51:31+0000",
  "field_data": [
    { "name": "investment_budget",      "values": ["₹5_cr+"] },
    { "name": "purpose_of_purchase",    "values": ["investment"] },
    { "name": "preferred_contact_time", "values": ["morning"] },
    { "name": "full_name",              "values": ["Rohan Mehta"] },
    { "name": "phone_number",           "values": ["+919800011111"] },
    { "name": "email",                  "values": ["rohan.mehta@example.com"] }
  ],
  "form_id": "2869657293379182",
  "ad_name": "Ad 1",
  "adset_name": "Ahmedabad + G'nagar",
  "campaign_name": "Leads_Dubai Properties_09/06/26"
}
```

### Sample lead 2: Event 4th-5th July form

```json
{
  "id": "1690200115622509",
  "created_time": "2026-06-29T17:58:13+0000",
  "field_data": [
    { "name": "full_name",                  "values": ["Aarav Shah"] },
    { "name": "phone_number",               "values": ["+919800022222"] },
    { "name": "email",                      "values": ["aarav.shah@example.com"] },
    { "name": "will_you_attend_the_event?", "values": ["yes,_5th_july"] },
    { "name": "what_is_your_primary_goal?", "values": ["investment"] }
  ],
  "form_id": "1623165265438269",
  "ad_name": "New Leads ad – Copy 2",
  "adset_name": "Ahmedabad+Gnagar",
  "campaign_name": "Leads_Event4th5thJuly_10/06/26"
}
```

### Field analysis (114 leads, 15 unique fields, 5 campaigns)

| Question name in Meta | Leads | Seen in form (campaign) | Suggested target in LMS |
|---|---:|---|---|
| `full_name` | 114 | All 5 forms | Name (standard) |
| `phone_number` | 114 | All 5 forms | Phone (standard) |
| `email` | 114 | All 5 forms | Email (standard) |
| `whatsapp_number` | 7 | Event 4th-5th July | Custom: WhatsApp number |
| `investment_budget` | 3 | Dubai Properties | Custom: Investment budget |
| `what_is_your_approximate_investment_budget?` | 15 | Uddhavbhai Personal (2 forms) | Custom: Investment budget (same field) |
| `purpose_of_purchase` | 3 | Dubai Properties | Custom: Purpose |
| `what_is_your_primary_purpose_for_investing_in_dubai_property?` | 15 | Uddhavbhai Personal (2 forms) | Custom: Purpose (same field) |
| `what_is_your_primary_goal?` | 96 | Event 4th-5th July, Event 5th-6th Sep | Custom: Purpose (same field) |
| `preferred_contact_time` | 3 | Dubai Properties | Custom: Preferred contact time |
| `will_you_attend_the_event?` | 89 | Event 4th-5th July, Event 5th-6th Sep | Custom: Event attendance |
| `when_would_you_like_to_attend_the_event?` | 7 | Event 4th-5th July | Custom: Event attendance (same field) |
| `when_are_you_planning_to_invest?` | 15 | Uddhavbhai Personal (2 forms) | Custom: Investment timeline |
| `city` | 15 | Uddhavbhai Personal (2 forms) | Custom: City |
| `job_title` | 39 | Event 5th-6th Sep | Custom: Job title |

Campaigns in the file: `Leads_Dubai Properties_09/06/26`, `Leads_Event4th5thJuly_10/06/26`, `Leads_Event5th-6thSep_23/08/26`, `Leads_UddhavbhaiPersonal_29/08/26`, `Leads_UddhavbhaiPersonal_Gujarat_12/08/26`.

Example values: `₹5_cr+`, `₹1.9_cr_–_₹3_cr`, `end_use_/_future_relocation`, `yes,_5th_july`, `within_3–6_months`, `just_exploring`, `Ahmedabad`.

### What the data teaches (build rules)

- **Forms differ and change.** Never assume a fixed set of questions. A form can gain a question later (for example 7 leads in the July event form have extra fields). New questions are flagged as unmapped, and the lead is still saved.
- **Many-to-one mapping is required.** The same idea is worded differently per form (three different "purpose" questions, three "budget" questions). The mapping UI must let several questions, from several forms, feed one custom field.
- **`values` is a list.** It may hold more than one answer. Store the list. For a single-value custom field use the first value, and join with ", " for display if there are several.
- **Phone numbers already arrive in E.164** (`+91...`). Still normalize and validate with `phonenumbers`. Keep the raw value too.
- **The lead carries campaign, ad set and ad names and `form_id` itself.** Save them on the Enquiry and in MongoDB. Names can contain quotes, slashes, en dashes and spaces (`G'nagar`, `ad – Copy 2`, `09/06/26`). Always use parameterized queries and UTF-8.
- **Text is Unicode** (`₹`, `–`). Use UTF-8 end to end, including exports (CSV with BOM for Excel).
- **Meta time format** is `2026-06-29T17:58:13+0000`. Parse as UTC, store UTC, display as DD/MM/YYYY in the workspace timezone.
- **Junk names exist** (for example `Rohan Mehta`). Do not validate names strictly. Trim only.
- **The lead `id` is the `leadgen_id`.** Use it as the idempotency key.

### Mapping this sample into the system (worked example, sample lead 2)

| Step | Result |
|---|---|
| MongoDB | One `lead_form_responses` document exactly as shown in section 3 |
| Contact | Match on `+919800022222`. Not found, so create Contact (name Aarav Shah, phone +919800022222, email aarav.shah@example.com) |
| Enquiry | New enquiry: source Meta, campaign `Leads_Event4th5thJuly_10/06/26`, ad set `Ahmedabad+Gnagar`, ad `New Leads ad – Copy 2`, form `1623165265438269`, status New, owner by assignment rule (default Unassigned), `leadgen_id` stored |
| Custom values | Event attendance = `yes, 5th july` (stored raw `yes,_5th_july`), Purpose = `investment`, if those mappings exist |
| Activity log | `enquiry_created` entry (and `repeat_enquiry` if the Contact already existed) |
| Live alert | Enquiry list updates in real time |

---

## 5. Roles and permissions (default matrix, adjust if the owner says so)

Roles: **Owner, Admin, Manager, Agent, Viewer**. Teams group users. Permission checks happen in the API (never only in the UI) and in queries.

| Capability | Owner | Admin | Manager | Agent | Viewer |
|---|:--:|:--:|:--:|:--:|:--:|
| Billing, plan, delete workspace | Yes | No | No | No | No |
| Invite users, set roles, manage teams | Yes | Yes | No | No | No |
| Statuses, custom fields, assignment rules | Yes | Yes | No | No | No |
| Connect / disconnect Meta Page, Manage Forms, field mapping | Yes | Yes | No | No | No |
| See all enquiries | Yes | Yes | Yes (own teams) | Own and assigned only | Read-only, per share |
| Create / edit enquiries, notes, calls, follow-ups | Yes | Yes | Yes | Yes (own) | No |
| Delete enquiry (soft) | Yes | Yes | Yes | No | No |
| Reassign owners | Yes | Yes | Yes | No | No |
| Import | Yes | Yes | Yes | No | No |
| Export (audited) | Yes | Yes | Yes | No | No |
| Reports and dashboard | All data | All data | Team data | Own numbers only | Read-only |
| Contacts | Read-only for everyone | Read-only | Read-only | Read-only | Read-only |

---

## 6. Business rules

### Contact and Enquiry (duplicate handling)

1. Contacts are **read-only**. Users cannot create, edit or delete them. Only the system writes them when an enquiry arrives.
2. Match key is per tenant: **Phone (default)** or **Email**. Phone is normalized to E.164 (default country from tenant setting, India +91). Email is lowercased and trimmed.
3. Key found: reuse the Contact, create a **new** Enquiry, mark it **Repeat Enquiry**, log `repeat_enquiry`.
4. If contact info differs: update the Contact and log `contact_information_updated`. Default rule: **only fill empty fields**, never overwrite (each Enquiry keeps its own submitted copy).
5. Leads with no phone: fall back to email. If both are missing, still create the Enquiry with a Contact that is never merged with others.
6. Phone is locked on an Enquiry after creation for normal users. (An Admin-only "Correct phone" action can come later.)
7. Deleting an Enquiry is a **soft delete**. When all Enquiries of a Contact are deleted, the Contact is auto-deleted (soft).
8. Concurrent webhooks for the same phone must not create two Contacts: use the unique partial index and handle the conflict by re-reading.

### Meta connection rules

1. One workspace can connect only **one Meta Page**. Enforced in the UI (single-select), in the API, and by a unique database constraint.
2. One Meta Page can belong to only one workspace (unique `page_id`). If the user tries a second Page, show: "Only one Meta Page can be connected. Disconnect the current Page first."
3. Only Owner and Admin can connect, change or disconnect the Page and forms.
4. Only **connected forms** create Enquiries. A lead from an unconnected form is saved in MongoDB with status `form_not_connected` and creates no Enquiry. Events from any Page other than the connected one are ignored.
5. Disconnecting Meta removes the Page's webhook subscription. Old Enquiries stay.
6. Meta tokens are stored encrypted. Show a banner when the token is expiring or expired.

### Status, follow-ups, calls

- Default statuses: New, Contacted, Qualified, Closed, Lost. Admin can rename, reorder, add. Every change goes to `status_history` and `activity_logs`.
- Follow-up: date, time, assignee. Shows under Upcoming or Overdue and on the dashboard.
- Call log: outcome, duration, notes. Timeline records `call_logged`.
- Owners: one primary owner plus any number of secondary owners. Default owner uses the assignment rules table. Ship "Unassigned" and "fixed owner by campaign or form". Round-robin is a later addition.

### Display rules (apply everywhere)

- **Date format DD/MM/YYYY** in lists, records, timeline, filters, date pickers, reports, exports and import files.
- **Tables:** default **25 rows** per page. User can choose **50, 100 or 200**. Pagination controls (first, previous, page numbers, next, last) and a total count. Paging is done on the server. Maximum page size is 200. Applies to Enquiries, Contacts, Manage Forms, import logs, sync logs and report tables. Export is not limited by page size.
- **Notifications:** in-app bell. First used for finished background imports, later also @mentions.

---

## 7. Flows

### F1. One-time setup for a new business

1. Create account and workspace (timezone, dedupe key Phone or Email).
2. Invite users, create Teams, assign roles.
3. Configure statuses.
4. Create custom fields (Enquiries only).
5. Connect Meta: Facebook login (OAuth), grant permissions, choose **one** Page.
6. Manage Forms: all forms of the Page are listed; click Connect on the forms you want.
7. Map form fields for each connected form (Name / Phone / Email, a custom field, or unmapped).
8. Send a test lead with Meta's lead testing tool and confirm the enquiry appears with campaign, ad set, ad and form.
9. Go live.

### F2. How a Meta lead enters the system

```
Person submits Instant Form
  -> Meta calls POST /webhooks/meta
  -> verify X-Hub-Signature-256, save raw event, reply 200 at once
  -> Celery job (idempotent on leadgen_id)
  -> worker fetches full lead from Graph API (campaign, ad set, ad, form)
  -> is the form connected in Manage Forms?
       no  -> keep raw lead in MongoDB with status form_not_connected, stop
       yes -> save lead in MongoDB (lead_form_responses)
  -> find or create Contact (dedupe) and create Enquiry with mapping (one PostgreSQL transaction)
  -> write activity_logs (enquiry_created, repeat_enquiry if relevant), apply default owner
  -> WebSocket live alert to the enquiry list
  -> failures go to failed_sync_logs with a Retry button
```

A scheduled **backfill poll** (Celery Beat) re-checks recent leads of connected forms so missed webhooks are recovered.

### F3. Daily user workflow

Open a Smart View (All Enquiries, My Enquiries, Unassigned, Calls Due Today), pick an enquiry, use quick actions (Call, WhatsApp, Email, Add Note), log the call, update status, schedule a follow-up, collaborate (secondary owners, @mentions, attachments). Managers use the Dashboard and Reports.

### F4. Bulk import

1. Upload CSV or Excel (size and type checked, rows counted, dates in DD/MM/YYYY).
2. Map columns to standard and custom fields.
3. Preview first rows and a duplicate summary. Nothing is saved yet.
4. Run: **up to 100 rows run live** and the result shows on screen. **More than 100 rows run as a background Celery job**, the user keeps working.
5. When a background import finishes, send an **in-app notification** (completed, or completed with errors) that opens the import log.
6. Import log shows created, linked to existing, failed. Download the failed-record report, fix, re-upload.

### F5. Connecting Meta and Manage Forms (Make.com style)

The pattern follows how Make.com connects Facebook Lead Ads: connect the Facebook account, choose the Page, make sure the app has leads access to the Page, then choose the Form. Here the user can connect more than one form of the Page.

1. **Settings > Integrations > Meta** shows "Not connected" and one **Connect Meta** button (Owner and Admin only).
2. Facebook login window (OAuth). Grant permissions for pages, leads and webhooks.
3. **Choose one Page** with single-select buttons.
4. **Check leads access.** The system tests that it can read leads from the Page. If not, show help: in Meta Business Suite open Integrations > Leads Access, select the Page, give access to this app, then click **Check again**.
5. **Manage Forms** opens. The system subscribes the Page to webhooks and loads all Instant Forms. Table columns: form name, form ID, status on Meta (Active or Archived), created date, connection status, leads received, **Connect / Disconnect** button. A **Refresh** button reloads forms.
6. User connects the forms they want. Connected forms go to field mapping.
7. Mapping: questions come from the stored form data. Many questions (from several forms) can map to one custom field.
8. **Disconnect or change Page:** disconnect first (removes webhook subscription), confirm the warning, then connect again.
9. An in-app **"How to connect" guide** on the Meta settings page: log in, choose Page, give Leads Access, connect forms, send a test lead.

---

## 8. UI and design direction (reference: https://www.superlist.com/)

The owner wants the app to feel like **Superlist**: a calm, fast, uncluttered workspace that is simple on the surface and powerful underneath. Take the *principles* below. Do not copy Superlist's branding, logo, text or images.

### Principles taken from the Superlist reference

| Superlist idea | How it applies in the LMS |
|---|---|
| Tasks and notes live together, so context stays in one place | An Enquiry opens as one page with details, notes, calls, follow-ups, attachments and the timeline together, no tab-hopping between apps |
| A simple, flexible system that is not overloaded | Few buttons visible, power features behind menus and keyboard shortcuts. Smart Views in the sidebar instead of many menus |
| Quick add from anywhere | A global quick-add (shortcut `Q` or `+`): add an enquiry, a note on the open enquiry, or a follow-up |
| Nested lists and sub-steps | Follow-ups with sub-steps are not required. Use the same feel for grouping: collapsible sections in the enquiry page and grouped timeline |
| Real-time collaboration | New leads appear live in the list. Show who else is viewing or editing an enquiry (later phase) |
| Fast, beautiful, small delightful details | Instant feel: optimistic updates, skeleton loaders, subtle transitions, tidy empty states |
| Reminders | Follow-up reminders appear in the in-app notification bell |

The exact colors, fonts and spacing of Superlist were **not** captured. If the owner adds screenshots to `docs/reference/ui/`, match them. Otherwise use this default: light theme with a dark-mode option, a neutral gray scale, one calm accent color, generous whitespace, rounded corners (8 to 12 px), 14 px base text, a clean sans-serif font (Inter), thin 1 px borders, soft shadows only on popovers. Define colors as design tokens in Tailwind config so the theme can change in one place.

### Layout

- **Left sidebar:** workspace switcher, Search, Smart Views (All Enquiries, My Enquiries, Unassigned, Calls Due Today), custom views (pin, rename, share), Contacts, Dashboard, Reports, Imports, Settings. Collapsible.
- **Main pane:** the table or the open record.
- **Enquiry page:** two columns. Left: contact and enquiry details, status, owners, custom fields, **Original form response** (from MongoDB, underscores shown as spaces). Right: tabs or sections for Timeline, Notes, Calls, Follow-ups, Attachments. Quick-action bar at the top: Call, WhatsApp, Email, Add Note.
- **Top bar:** global search, quick add, notification bell, user menu.
- Fully responsive. Agents will use it on phones, so the enquiry page and quick actions must work well on a small screen.
- Keyboard shortcuts for common actions, with a shortcut help dialog (`?`).
- Accessible: focus states, labels, color contrast.

### Screens to build

1. Sign up, log in, accept invite, forgot password
2. Onboarding wizard (workspace, invite users, statuses, connect Meta)
3. Enquiry list (table, filter bar, view tabs, bulk actions, page-size selector 25/50/100/200, pagination, live new-lead indicator)
4. Enquiry detail page (as above)
5. Contacts list and Contact page (read-only, related enquiries)
6. Manage Forms (table with Connect / Disconnect, Refresh)
7. Meta settings with connection guide, leads-access check, failed sync logs, sync history
8. Field mapping screen (many-to-one into custom fields, shows sample values from stored form data)
9. Import wizard (upload, map, preview, run) and Import log (with failed-record download)
10. Saved views manager, filter builder (AND / OR groups)
11. Dashboard (8 fixed widgets, see below) and Reports
12. Settings: users and roles, teams, statuses, custom fields, assignment rules, workspace (timezone, dedupe key, default country), plan and usage
13. Notification center (bell dropdown plus full page)

**Dashboard widgets (proposed, 8 fixed):** New leads today, Unassigned enquiries, My follow-ups due today, Overdue follow-ups, Leads by source, Leads by status, Conversion rate, Daily activity. Widgets respect role visibility.

---

## 9. API outline (REST, versioned under `/api/v1/`)

All endpoints are tenant-scoped from the authenticated membership. Lists use `page` and `page_size` (allowed: 25, 50, 100, 200; default 25) and return `count`, `next`, `previous`, `results`.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/forgot-password`, `/auth/accept-invite` |
| Workspace | `GET/PATCH /workspace`, `GET/POST /users`, `PATCH /users/{id}/role`, `GET/POST /teams` |
| Statuses and fields | `GET/POST/PATCH /statuses`, `GET/POST/PATCH /custom-fields` |
| Contacts | `GET /contacts`, `GET /contacts/{id}` (read-only) |
| Enquiries | `GET/POST /enquiries`, `GET/PATCH/DELETE /enquiries/{id}`, `POST /enquiries/bulk`, `GET /enquiries/{id}/timeline`, `GET /enquiries/{id}/form-response`, `POST /enquiries/{id}/notes`, `/calls`, `/followups`, `/attachments` |
| Views and search | `GET/POST/PATCH/DELETE /views`, `GET /search?q=` |
| Import / export | `POST /imports`, `POST /imports/{id}/map`, `GET /imports/{id}/preview`, `POST /imports/{id}/run`, `GET /imports`, `GET /imports/{id}/failed-report`, `POST /exports` |
| Meta | `GET /meta/status`, `POST /meta/connect`, `GET /meta/callback`, `GET /meta/pages`, `POST /meta/page` (single), `POST /meta/check-access`, `DELETE /meta/connection`, `GET /meta/forms`, `POST /meta/forms/refresh`, `POST /meta/forms/{id}/connect`, `POST /meta/forms/{id}/disconnect`, `GET/PUT /meta/forms/{id}/mapping`, `GET /meta/sync-logs`, `GET /meta/failed-syncs`, `POST /meta/failed-syncs/{id}/retry` |
| Webhook | `GET /webhooks/meta` (verification), `POST /webhooks/meta` (events, signature checked) |
| Reports | `GET /reports/{name}`, `GET /dashboard` |
| Notifications | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Live | WebSocket `/ws/tenant/` for new-lead and notification events |

Filter engine: a JSON tree of AND / OR groups is accepted by `GET /enquiries?filter=<json>`. It is converted to **safe, parameterized** queries (whitelist of fields and operators, never string concatenation).

---

## 10. Reports

Ready-made reports (today / week / month): by source, campaign, form, owner, status, follow-up due, conversion, repeat enquiries, daily activity. All read from PostgreSQL only. Report totals must equal raw database counts. Agents see only their own numbers. Dates in DD/MM/YYYY. Table results are paginated.

---

## 11. Security and quality requirements

- **Tenant isolation everywhere:** PostgreSQL Row Level Security (set `app.tenant_id` per request/connection) plus tenant-scoped ORM queries, plus the MongoDB data layer. An automated test creates two tenants and proves one cannot read or write the other's data in PostgreSQL, MongoDB, files and WebSocket channels.
- Passwords: argon2. Short-lived JWT access tokens, rotating refresh tokens, rate-limited login, email verification and password reset.
- Webhook: verify `X-Hub-Signature-256` with the app secret using a constant-time compare. Reply fast, process in Celery. Idempotent on `leadgen_id`.
- Secrets and Meta tokens encrypted at rest. No secrets in logs.
- Input validation on every endpoint. Parameterized queries only. File uploads: type and size checked, stored in S3-compatible storage, served by signed URL.
- Exports are permission-gated and written to the audit log.
- Performance targets: list of 10,000+ enquiries with a custom-field filter responds quickly (add the right indexes); a 200-row page loads quickly; a Meta test lead appears as an Enquiry within seconds.
- Backups: daily for PostgreSQL and MongoDB, with a tested restore.
- Privacy: privacy policy page and data-deletion URL (Meta requires both and India DPDP needs them).
- Tests: unit tests for rules (dedupe, mapping, permissions), API tests, ingestion tests using the reference JSON files, and the tenant-isolation suite. CI runs lint, type-check and tests.
- Code: TypeScript strict mode, ESLint and Prettier on the frontend; `ruff` and `black`, type hints, on the backend.

---

## 12. Phase-wise build plan

Build one phase at a time. Test it, then move on. Effort is a rough guide for a small team working with Claude Code.

### Phase 0: Foundation (1 to 2 weeks)

**Goal:** A secure, empty application shell that everything else sits on.

**Build**
- Monorepo (`web` React + TypeScript + Tailwind, `api` Django), Docker Compose with PostgreSQL, MongoDB and Redis, CI pipeline
- Auth (login, refresh tokens), tenants, users, memberships
- Roles and permission matrix, Teams
- Tenant guard (Django middleware) + Row Level Security in PostgreSQL, and the MongoDB data layer that always adds `tenant_id`
- Base UI layout and navigation (Superlist-style shell: sidebar, top bar, empty states)
- Shared UI pieces: date helper (DD/MM/YYYY, workspace timezone) and a reusable data table with 25 default rows, 50 / 100 / 200 options and pagination
- i18n set up (English only, no hardcoded text)

**Done when:** A user can sign up, invite another user, log in with a role, and cannot see another tenant's data in PostgreSQL or MongoDB (a test proves it).

### Phase 1: Core CRM, Contacts and Enquiries (2 to 3 weeks)

**Goal:** Everything needed to work an enquiry manually.

**Build**
- Enquiry ingestion service with duplicate detection and auto Contact create / update (used later by Meta and import)
- Contacts (read-only) with related enquiries view
- Enquiries: create, edit, soft delete, primary + secondary owners, configurable statuses
- Notes, follow-ups, call logs, attachments in PostgreSQL
- Activity timeline written to MongoDB `activity_logs` (field, status and assignment changes included), status history in PostgreSQL
- Enquiry detail page and quick-action bar

**Done when:** A user can create an enquiry, see the Contact auto-created, repeat the same phone and get a second enquiry on the same Contact (marked Repeat), and see the full timeline loaded from MongoDB.

### Phase 2: Views, Filters, Search, Custom Fields (2 weeks)

**Goal:** Find the right enquiries quickly.

**Build**
- Custom fields (enquiries only) with typed validation
- Filter engine with AND / OR groups (JSON to safe SQL), quick filters, date filters
- System smart views and custom views (save, rename, share, pin)
- Global, phone, email, campaign, form and custom-field search
- Bulk actions and quick actions
- Table view with server-side pagination: 25 rows by default, 50 / 100 / 200 options, page numbers and total count

**Done when:** Saved views return correct results and counts, a filter on a custom field works with 10,000+ test enquiries without slowness, and a page of 200 rows loads quickly.

### Phase 3: Import and Export (1 week)

**Goal:** Bring in existing data and take filtered data out.

**Build**
- CSV / Excel import with mapping, preview, duplicate detection and logs. Dates read as DD/MM/YYYY
- Up to 100 rows import live. More than 100 rows import as a background job
- Basic in-app notification center: a notification when a background import completes
- Failed-record report download
- Export of the current filtered or saved view (permission-gated and audited)

**Done when:** A 100-row file imports live. A 5,000-row file imports in the background, a notification arrives when it finishes, duplicates link to existing Contacts, and failed rows can be downloaded and fixed.

### Phase 4: Meta Ads Integration (2 to 3 weeks)

**Goal:** Real-time lead capture with no third-party automation tool.

**Build**
- Meta OAuth, webhook endpoint with signature check, Celery worker
- Page selection limited to **one Page per workspace**, enforced in UI, API and a unique database constraint; one Page cannot be linked to two workspaces
- Leads-access check with help text, Disconnect Meta (removes webhook subscription), and the in-app "How to connect" guide (Make.com style)
- **Manage Forms** screen: lists all forms of the Page, Connect / Disconnect per form, Refresh. Only connected forms create enquiries
- Campaign, Ad Set, Ad, Instant Form detection (form detection toggle in settings)
- Raw lead storage in MongoDB `lead_form_responses` (unique on tenant + `leadgen_id`), new-question detection, field mapping UI and edit with many-to-one mapping into custom fields
- Lead sync history, failed sync logs with retry, scheduled backfill, token-expiry banner
- Ingestion tests that replay the two sample lead JSON files

**Done when:** A real test lead from a connected form appears as an Enquiry within seconds, with correct campaign data. The original form response is visible on the enquiry (from MongoDB) and the mapped answers are filterable. A lead from an unconnected form creates no enquiry. A second Page cannot be connected. A failed sync can be retried without creating a duplicate.

### Phase 5: Reports, Dashboard, Mentions (1 to 2 weeks)

**Goal:** Management visibility.

**Build**
- All ready-made reports (today / week / month, by source, campaign, form, owner, status, follow-up due, conversion, repeat enquiries, daily activity), read from PostgreSQL only, dates in DD/MM/YYYY
- Dashboard with the 8 fixed widgets, respecting role visibility
- @mentions added to the notification center built in Phase 3

**Done when:** Report totals match raw counts in the database and an Agent sees only their own numbers.

### Phase 6: Hardening and SaaS Readiness (1 to 2 weeks)

**Goal:** Make it safe and ready for paying customers.

**Build**
- Permission and tenant-isolation test suite covering PostgreSQL and MongoDB (includes the single Meta Page rule), performance tuning, view-count caching
- Audit log review, monitoring (Sentry), backups with tested restore for both PostgreSQL and MongoDB
- Plans and usage limits, billing hooks, onboarding wizard

**Done when:** The security checklist passes, a load test is acceptable, and a new tenant can onboard without help.

---

## 13. Work to start in parallel (owner tasks, not code)

1. **Meta App Review and Business Verification:** start during Phase 0 or 1. It takes time and real clients cannot connect until approved. Test with your own Page and Meta's test leads meanwhile.
2. **Privacy policy and data deletion URL:** required by Meta and by India DPDP.
3. **Domain, SSL, email sender:** app domain, API subdomain, verified sending domain for invites and alerts.
4. **Hosting and backups:** choose a host (single VPS or managed cloud, India region), and enable daily backups for PostgreSQL and MongoDB. Plan hosting for both databases and Redis.
5. **Sample data:** a real sample Excel file (dates in DD/MM/YYYY) and a sample Instant Form. The three reference JSON files already cover the Meta side.
6. **Connection guide content:** screenshots and short steps for the "How to connect" guide: Facebook login, choose Page, Leads Access, Manage Forms, test lead.
7. **UI screenshots:** optional, add Superlist (or other) screenshots to `docs/reference/ui/` to match the look more closely.

### Not in the MVP (keep the design ready)

Auto-calling through a third-party tool, Conversions API sync back to Meta, WhatsApp / email new-lead alerts, Google Ads lead form, Opportunities module, scheduled report emails. These plug into the same ingestion service and the call-log tables later (keep a nullable `provider` column on call logs and a generic webhook-event pattern).

---

## 14. Open decisions and the defaults to use

The owner has not finalized these. **Use these defaults unless the owner says otherwise,** and keep each one behind a setting or a single code location so it is easy to change.

| # | Decision | Default to build |
|---|---|---|
| 1 | Phone handling | Default country India (+91), per-tenant setting. Store E.164 and keep the raw value. No phone: fall back to email; if both missing, create the Enquiry with an unmerged Contact. Never drop a lead |
| 2 | Editing phone | Locked after creation for normal users. Admin-only "Correct phone" action is a later addition |
| 3 | Contact auto-update | Fill empty fields only, never overwrite. Each Enquiry keeps its own submitted copy. Log `contact_information_updated` when a blank field is filled |
| 4 | New field mappings | Apply to new enquiries only. Optional Admin action "Re-apply mapping to existing enquiries" (with preview and count, audited) comes later |
| 5 | Default owner | Unassigned, with an `assignment_rules` table (priority, condition campaign or form, strategy fixed owner). Round-robin later, using a proper lock |
| 6 | Auth | Build on Django with proven libraries (argon2, JWT with rotating refresh). 2FA and Google login later |
| 7 | Hosting and budget | India region, Docker, stateless app, files in S3-compatible storage, managed databases if the budget allows |
| 8 | Languages | English at launch, translation-ready, UTF-8 everywhere (Hindi and Gujarati text must save and search correctly) |
| 9 | Later features | After Phase 6, in this order: WhatsApp / email new-lead alerts, auto-calling, Conversions API |

---

## 15. Environment variables (create `.env.example`)

```
# Django
DJANGO_SECRET_KEY=
DJANGO_DEBUG=false
ALLOWED_HOSTS=
CORS_ALLOWED_ORIGINS=
FIELD_ENCRYPTION_KEY=            # encrypts Meta tokens at rest

# PostgreSQL
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=
POSTGRES_PORT=5432

# MongoDB
MONGO_URI=
MONGO_DB_NAME=lms

# Redis / Celery / Channels
REDIS_URL=

# Meta
META_APP_ID=
META_APP_SECRET=
META_WEBHOOK_VERIFY_TOKEN=
META_GRAPH_VERSION=
META_OAUTH_REDIRECT_URI=

# Storage (S3-compatible)
S3_ENDPOINT=
S3_BUCKET=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_REGION=

# Email
EMAIL_HOST=
EMAIL_PORT=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=

# Monitoring
SENTRY_DSN=

# Frontend
VITE_API_BASE_URL=
VITE_WS_URL=
```

---

## 16. Starter prompt for the owner to give Claude

Copy this as your first message after adding this file to the repo:

> Read `LMS_PROJECT_SPEC.md` fully, plus the files in `docs/reference/`. We are building the LMS Project. Start with **Phase 0 only**. First list the folder structure and the main files you will create, then build Phase 0, add the tests for its "Done when" check, and tell me how to run everything with Docker Compose. Do not start Phase 1 until I say so.

For each next phase, send: "Phase N is approved. Read section 12 for Phase N+1 and build only that phase. Run all earlier tests too."
