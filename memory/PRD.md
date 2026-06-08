# RouteMail - Email Rotation SaaS Platform


## Changelog — Iteration 49 (June 2026)

### Blog Permission Management
- New per-user permission `can_manage_blogs` (boolean, default false) — independent of role / subscription / campaign permissions.
- New backend dependency `get_blog_manager_user` — allows access when `role == "super_admin"` OR `can_manage_blogs == true`. Replaces `get_super_admin_user` on all 6 `/api/admin/blogs*` endpoints (list/create/read/update/delete + image upload).
- New endpoint `PUT /api/admin/users/{user_id}/blog-permission` (super_admin only) — body `{can_manage_blogs: bool}`. Records `blog_permission_updated_at` + `blog_permission_updated_by` and writes to `admin_logs`.
- `/api/auth/me` now returns `can_manage_blogs`.
- `/api/admin/users` listing now includes `can_manage_blogs` per user.

### Blog Backup & Restore
- New endpoint `GET /api/admin/backup/blogs/export` (super_admin only) → ZIP with `metadata.json` + `blogs.json`. Featured images preserved inline as base64 data-URIs inside `blogs.json` (per design).
- New endpoint `POST /api/admin/backup/blogs/export` with `{blog_ids:[...]}` (super_admin only) → ZIP of selected blogs only.
- New endpoint `POST /api/admin/backup/blogs/import?conflict=skip|merge|replace|copy` (default `copy`) — restores blogs from a backup ZIP. Works with blog-only and full-platform exports.
  - **copy** (default): inserts a new blog with fresh `blog_id`, slug suffix `-imported`, title suffix `(Imported)`.
  - **skip**: leaves existing blog untouched.
  - **merge**: updates the existing blog with imported fields (preserves `blog_id` + `slug`).
  - **replace**: replaces the existing blog in place (preserves `blog_id` + `slug`).
- `POST /api/admin/backup/export/users` now accepts optional `include_blogs: bool` — when true, bundles `blogs.json` (all platform blogs) into the selected-users ZIP. Default false.

### Frontend
- **Sidebar**: new `Blog Management` link (testid `nav-blog-management`) visible to super_admin OR users with `can_manage_blogs`.
- **AdminBlogs** (`/admin/blogs`): permission gate relaxed — now reachable by any user with `can_manage_blogs`. Back button routes non-super-admins to `/dashboard`.
- **AdminDashboard** Users table: new blog-permission toggle per row (testid `blog-permission-toggle-{user_id}`) — disabled for super_admins (always-on by virtue of role).
- **SystemBackupRestore**: new `Blog Backup & Restore` section (testid `sys-backup-blogs-section`) with `Export All Blogs`, `Export Selected Blogs`, `Import Blogs` flows. New `Include Blogs` checkbox on the Export Selected Users section.

### Verification
- Iteration 49 test report: 28/28 backend tests pass (grant + revoke + 403/200 enforcement + all 4 conflict modes + invalid-ZIP handling + regression on existing /campaigns /drip-campaigns /accounts /dne-lists /unibox/replies /auth/me). Frontend testids verified at source level + live smoke screenshots (admin dashboard + system backup page).
- `retest_needed: false`.


## Changelog — Iteration 48 (June 2026)

### Stripe secret rotation + dashboard support footer
- **STRIPE_SECRET_KEY rotated** in `/app/backend/.env` to the new value (`sk_live_...IrhIp5Dk`). Old key removed completely — confirmed via grep across /app (excluding /.git). New key appears in exactly one file: `/app/backend/.env`. Frontend bundles never see it.
- Stripe library accepted the new key cleanly (`/api/subscription/prices` 200, no `AuthenticationError` in backend logs after restart).
- **Sidebar support footer** added at the bottom of the `<aside>` (testid `sidebar-support-footer`) — renders unconditionally for every page that mounts Sidebar (Dashboard, Campaigns, Drip, Email Accounts, Email Lists, Unibox, Leads, Do Not Email, Subscription, Backup, Admin pages). Contains an `<a href="mailto:support@routemail.co" data-testid="support-email-link">`. Hidden on /login because Sidebar isn't rendered there.
- Mobile responsive at 390px (no horizontal overflow).

### Drive-by fix (surfaced by tester)
- `check_subscription_active()` was crashing 500 for any user whose `plan_type` field exists in Mongo but is `None` (e.g. seeded super-admin). `user.get('plan_type', 'free')` returns the stored `None` rather than the default. Fixed with `user.get('plan_type') or 'free'` (and same for `subscription_status`). `/auth/me` now returns 200 for the super-admin.

### Verification
- Backend: `/api/auth/me`, `/api/subscription/prices`, `/api/campaigns`, `/api/drip-campaigns`, `/api/email-accounts`, `/api/unibox/replies`, `/api/dne-lists` all 200 with the new key + the /auth/me fix.
- Secret-key grep: new key in one file only; old key fully absent.
- Frontend: 10/10 dashboard pages render the footer; /login correctly excludes it.


## Changelog — Iteration 47 (June 2026)

### Free Forever Plan replaces 14-day trial
- **Concept removed**: no more 14-day trial, no `trialing` status for new users, no `trial_ends_at` expiry checks. New users land on a permanent Free Plan.
- **Limits**: 500 monthly unique recipients + 3 email accounts (same numbers the old trial used).
- **Backend** — `check_subscription_active()` rewritten:
  - Free Plan returns `{active:True, plan:'free', status:'active'}` — never expires.
  - Legacy users stored with `subscription_status='trialing'` or `'expired'` are auto-migrated on read.
  - Paid plan `past_due` + grace_period_end passed → `_downgrade_to_free_plan(reason='grace_expired')`.
  - Paid plan `canceled` + billing_cycle_end passed → `_downgrade_to_free_plan(reason='canceled_cycle_ended')`.
  - Stripe webhook `customer.subscription.deleted` keeps the user on their paid plan until cycle end, then downgrades lazily.
- **New helper `_downgrade_to_free_plan(user_id, reason)`**: idempotent; clears stripe_subscription_id + grace fields, records `downgraded_to_free_at` + `downgrade_reason`.
- **Admin `/assign-plan` extended**: accepts `free` plus all custom_* slugs. Assigning `free` to a user who was already on free does NOT record a downgrade event (avoids false downgrade banner).
- **Email + Google registration paths** now set `plan_type='free'`, `subscription_status='active'`, `trial_ends_at=null`.
- **Welcome email + admin signup notification** wording updated — no more "14-day trial".
- **`/api/auth/me`** now returns `downgraded_to_free_at` + `downgrade_reason`.
- **`/api/subscription/prices`** `free_plan` now: `{name:'Free', free_forever:true, price_usd:0, ...}` — `trial_days` key removed.

### Frontend
- **Landing pricing grid** is now 4 cards (Free / Starter / Growth / Custom). New `pricing-card-free` shows `$0/year` + "Free forever — no credit card" footnote. CTA testids renamed `header-start-free-btn` + `hero-start-free-btn`. FAQ updated.
- **Subscription page**: replaced Trial-Expired alert with a `downgrade-notice` banner (only shown to users actually downgraded). Free card has disabled `free-plan-current-btn` with text "Current Plan" for free users.
- **Dashboard**: free-plan banner reads "You're on the Free Plan — Free forever — upgrade any time…". No more "X days left in trial".
- **AdminDashboard**: Trial Active / Trial End fields replaced with Plan Source + Downgraded From (testids `sub-plan-source`, `sub-downgraded-from`).
- **Register subtitle + LiveDashboardDemo toast** rewritten to drop trial wording.

### Verification
- Backend pytest `/app/backend/tests/test_iteration_47_free_plan.py` — 15/15 pass (covers prices payload, new-user defaults, legacy-data migration, both grace-expired and cancel-cycle downgrade paths, admin assign-free + assign-starter + remove-override, regression on /campaigns /drip-campaigns /dne-lists /accounts /unibox).
- Frontend Playwright on Landing — 17/17 assertions pass live.
- Polish nits flagged by tester both fixed: `/auth/me` now includes the two new fields, and admin assign-free skips the downgrade-event fields when the target was already free.


## Changelog — Iteration 46 (June 2026)

### Cloudflare Turnstile CAPTCHA on /login + /register only
- **Backend** — `verify_turnstile_or_raise(token, http_request)` helper (~`server.py` L1999) POSTs to `https://challenges.cloudflare.com/turnstile/v0/siteverify` with the secret key. Wired as the **first line** of both `/api/auth/login` and `/api/auth/register` — runs before any user lookup, password hash check, or DB insert. Failures return HTTP 400 with the exact message **"Security verification failed. Please try again."**. Missing-token / bogus-token / whitespace-token all rejected. Tested register failure does NOT persist a user.
- **Frontend** — new `Turnstile.jsx` component lazily injects the Cloudflare `api.js` script (singleton; only one script tag per page) and renders the explicit widget. Exposes a `widgetRef.reset()` for the parent to call after a failed auth attempt.
- **Login.jsx + Register.jsx** — both render the widget below the submit button (testids `login-turnstile-wrapper`, `register-turnstile-wrapper`). Submit buttons are **disabled until the token is solved** (when `REACT_APP_TURNSTILE_SITE_KEY` is set). On error the widget auto-resets so the user can try again.
- **Secret-key audit passed** — grep across all 10 frontend JS bundles confirms `TURNSTILE_SECRET_KEY` (`0x4AAAAAADgY3dK_B7t1fZDG7db_iCbUzpk`) does NOT appear in any bundle or DOM. Only the site key is exposed.
- **Mobile responsive** — `scrollWidth == innerWidth == 390` at iPhone 14 width on both pages.
- **No other endpoints gated** — `/api/campaigns`, `/api/drip-campaigns`, `/api/dne-lists`, `/api/unibox/replies`, `/api/accounts` all unchanged (verified).

### Verification
- Backend pytest `/app/backend/tests/test_iteration_46_turnstile.py` — 10/10 passing.
- Frontend Playwright — widget renders, script injected exactly once, secret key absent from bundles, submit buttons disabled, mobile fits 390px. Happy-path (CAPTCHA solved) cannot be tested headlessly — that is the design intent of CAPTCHA.


## Changelog — Iteration 45 (June 2026)

### Unibox status section — compact + scalable
- **Removed** the per-account grid that listed every connected inbox (which made the page intolerably tall for users with 50–100+ accounts).
- **Replaced** with a single compact `unibox-status-card` showing `Receiving Accounts: <healthy> / <total>` + a one-line health summary.
- **Green / healthy state**: emerald border + check icon + "All connected inboxes are receiving successfully.".
- **Amber / issues state**: amber border + warning icon + "N account(s) require(s) attention." + a `View Issues` button that opens a focused `issues-dialog` listing ONLY problematic accounts.
- **Status classification** (`classifyAccountStatus(a)`): Receiving (healthy) / Delayed Sync (last sync > 24h) / Not Receiving (no IMAP) / IMAP Authentication Failed (error matches auth/535/credentials) / Connection Timeout (error matches timeout/connection refused) / Error (fallback). Each issue card shows the label + detail + last-successful-sync timestamp.
- **Refresh** button now re-fetches both replies AND status (was only replies before).
- Account-filter dropdown still lists every account (regression-safe).
- Mobile responsive at 390px — no horizontal overflow.

### Verification
- Frontend Playwright run — 12/12 acceptance criteria pass on a test account with 3 IMAP-unconfigured inboxes (exercises the amber path).
- DOM scan confirms old `account-status-grid` + `account-status-*` testids are fully removed.
- Backend smoke skipped per scope (no backend changes).


## Changelog — Iteration 44 (June 2026)

### Part 1 — Honest spell-check UI
- Replaced the misleading green "Spellcheck: Active" pulse badge (which always claimed Active regardless of the browser's actual setting) with a neutral amber-dot **"Test spell-check"** button.
- The button now opens a Popover (`editor-spellcheck-popover`) that:
  - Explains we rely on the browser's native spell-checker (no paid API).
  - Tells the user that if no red squiggle appears after testing, their browser's spell-check setting is off — and gives the exact path to enable it in Chrome / Edge / Safari / Firefox.
  - Hosts the `editor-spellcheck-insert-btn` that inserts the word **definately** at the caret. No misleading success toast.
- contentEditable still has `spellcheck="true"`, `lang="en"`, `autocorrect="on"`; HTML-mode textarea + plain-text fallback identical. `::spelling-error` CSS rule kept (renders custom red wavy underline when the browser flags a word).
- Helper text below the editor now reads: *"Spell-check is handled by your browser — click Test spell-check if you don't see red underlines."*

### Part 2 — LiveDashboardDemo mobile responsiveness
- **Zero page-level horizontal overflow** at 360 / 390 / 430 / 1440 px (verified `scrollWidth == innerWidth` at all four widths).
- **Tab strip**: now horizontally scrollable (`overflow-x-auto`, `snap-x`) on mobile and `flex-wrap` on desktop — all 11 demo tabs reachable on iPhone SE width.
- **Mobile section header** (`md:hidden`) replaces the desktop sidebar at the top of the demo panel — shows current section icon + label + Growth-plan badge.
- **Wide tables** (Campaigns, Email Accounts, Warmup, Leads, DNE entries) now sit inside `overflow-x-auto` wrappers with `min-w-[Xpx]` inner shells. Tables scroll internally; the page itself does not.
- Dashboard's main 2-column rail switched from `md:grid-cols-[1fr_300px]` → `grid-cols-1 lg:grid-cols-[1fr_300px]` so the side rail stacks below stats on tablets too.
- Panel padding now `p-3 sm:p-5 md:p-7` and panel wrapper has `overflow-x-hidden w-full max-w-full`.

### Verification
- Frontend Playwright run at 360 / 390 / 430 / 1440px — every responsive assertion passed, all 11 demo panels reachable at both extremes. Spellcheck Popover content + amber-dot button + insert flow + helper-text wording all confirmed.
- Backend smoke skipped per task scope (no backend changes).


## Changelog — Iteration 43 (June 2026)

### Spellcheck visibility audit & fix
- **`<style>` block** in RichTextEditor now ships explicit `::spelling-error { text-decoration: red wavy underline; text-decoration-skip-ink: none }` and `::grammar-error { text-decoration: blue wavy underline }` rules so Tailwind / prose can't suppress the browser's native squiggle.
- **contentEditable** gains `lang="en"`, `autoCorrect="on"`, `autoCapitalize="sentences"` in addition to `spellCheck={true}` — Chrome / Edge / Safari require these to render the squiggle on a contentEditable surface.
- **HTML-mode textarea** flipped from `spellCheck={false}` → `spellCheck={true}` + same `lang` / `autoCorrect` attributes.
- **Plain-text fallback textarea** mirrored with the same set of attributes for parity.
- **Toolbar indicator-button** (`data-testid=editor-verify-spellcheck-btn`) added: shows a pulsing emerald dot + the text `Spellcheck: Active · Verify`. Clicking it inserts `definately` into the editor at the caret (Visual mode uses execCommand with createTextNode fallback; HTML mode appends to `htmlDraft`). A sonner toast confirms the action.
- All existing editor features (image insertion + resize + delete, unsubscribe-link popover, variable insertion, link insertion, HTML toggle) are unchanged.

### Verification
- Frontend Playwright run — every attribute / CSS rule / button behaviour confirmed in BOTH the Campaign editor and the Drip step composer. Backend skipped (no backend changes this iteration).


## Changelog — Iteration 42 (June 2026)

### Campaign editor & management upgrades
- **Delete-image toolbar**: Selecting an `<img>` in the RichTextEditor now shows a floating "Delete Image" button (testid `delete-image-btn`) alongside the existing resize handles. Pressing `Delete` / `Backspace` while an image is selected also removes it. Surrounding text/content is preserved and `onChange` fires immediately. Fixed a pre-existing duplicate `onBlur` attribute that was masking `handleEditorBlur`.
- **Spell check**: Native browser spell check enabled on both the contentEditable visual editor and the plain-text fallback (`spellCheck={true}`). Helper text added under the editor — *"Spell check uses your browser's built-in spell checker."*
- **Export / Import for normal campaigns** — new endpoints:
  - `GET  /api/campaigns/{id}/export` — returns JSON wrapper `{schema_version:1, type:'campaign', exported_at, campaign:{name, from_name, subject, body, body_text, list_name, account_emails, dne_list_names, send_range_*, schedule_*, add_unsubscribe_footer, tracking_opens, tracking_clicks, created_at}}`. Operational fields (sent logs, recipient progress, analytics, replies) NEVER exported.
  - `POST /api/campaigns/import` — accepts the export payload, always saved as **draft**. Name uniqueness: `Name (Imported)` → `Name (Imported 2)` → …. Lists / accounts / DNE lists are resolved by name / email; missing matches silently fall back to empty.
- **Export / Import for drip campaigns**:
  - `GET  /api/drip-campaigns/{id}/export` — same wrapper for drips, includes every step with `delay_days` + `delay_hours`, schedule, stop conditions, tracking + unsubscribe footer.
  - `POST /api/drip-campaigns/import` — always saved as **draft**, same name-uniqueness rule. Zero-step or wrong-type payloads return 400.
- **Convert normal campaign → drip**:
  - `POST /api/campaigns/{id}/convert-to-drip` creates a NEW drip in draft status. The source campaign's subject/body becomes Step 1, with `from_name`, `account_ids`, `suppression_list_ids`, `tracking_opens`, `tracking_clicks`, `add_unsubscribe_footer` all mapped over.
  - Source campaign is **never** modified or deleted — verified end-to-end.
  - UI: Campaigns list row now has icon buttons for Export, Convert-to-Drip (Workflow icon) and Duplicate; Campaigns + Drip pages have new `Import` buttons in headers.

### Verification
- Backend pytest `/app/backend/tests/test_iteration_42_export_import_convert.py` — 18/18 passing.
- Frontend Playwright — every required testid + flow verified, convert-to-drip confirmed non-destructive.


## Changelog — Iteration 41 (June 2026)

### Unsubscribe + Domain Suppression + Super Admin Backup
- **Signed-token unsubscribe**: New `/api/unsubscribe/u/{token}` endpoint (HMAC-SHA256 signed, no internal IDs in URL). Legacy `/api/unsubscribe/{user_id}/{email}` retained for already-sent emails. Both return a styled HTML confirmation page.
- Unsubscribe pipeline now mirrors entries into the user's Global DNE list **and** stops any active/paused drip sequences for that contact in one transaction.
- **Domain-based suppression**: DNE lists now accept full emails (`john@example.com`) AND bare domains (`example.com`, `@example.com`). Each entry carries a `type` field (`email`|`domain`). Domain entries block every recipient on that domain across campaigns, drip campaigns, scheduled campaigns and warmup test sends.
- New endpoint `GET /api/dne-stats` reports `{ emails_blocked, domains_blocked, total_blocked }` — surfaced as a banner on the Do Not Email page.
- DoNotEmailDetail Add dialog has an Email Address / Domain pill selector with mode-specific placeholders.
- Unibox bulk "Add to Global DNE" dialog now offers Email Only vs Entire Domain scope.
- DNE CSV import/export now uses columns: `list_name, type, value, source, added_at, notes` (was `list_name, email, source, added_at`).
- Backup export `do_not_email_lists.json` preserves the `type` field on every entry.

### Super Admin System Backup & Restore (NEW)
- New module `/app/backend/admin_backup_routes.py` mounted at `/api/admin/backup/*`. Visible/usable only by `super_admin`.
- Endpoints:
  - `GET  /api/admin/backup/export/full` — ZIP of EVERY user + all their data (users.json, campaigns.json, drip_campaigns.json, email_accounts.json, email_lists.json, do_not_email_lists.json, responses_leads.json, subscriptions.json, plans.json, blogs.json, system_settings.json, per_user_data.json, metadata.json).
  - `POST /api/admin/backup/export/users` — ZIP for selected user_ids only.
  - `POST /api/admin/backup/import/preview` — Returns metadata + summary counts.
  - `POST /api/admin/backup/import?conflict={skip|merge|replace}` — Restores backup. Existing user passwords are NEVER overwritten. `merge` regenerates per-user record IDs to avoid collisions; `replace` wipes per-user collections first.
  - `GET  /api/admin/backup/history` — Auto-logged backup history (date, type, file size, user count).
- Security: `password_hash`, `verification_token`, `reset_token`, `session_token`, `captcha_secret`, `stripe_webhook_secret`, plain `smtp_password`/`imap_password` and plain `password` fields are STRIPPED from every export. Fernet-encrypted SMTP/IMAP blobs are preserved as-is.
- New page `/app/frontend/src/pages/SystemBackupRestore.jsx` mounted at `/admin/system-backup`. New sidebar link (`nav-system-backup`) visible only to super_admin.

### Verification
- Backend pytest suite `/app/backend/tests/test_iteration_41_unsubscribe_admin_backup.py` — 21/21 passing.
- Frontend Playwright run — all required testids confirmed live, admin gate enforced.

## Original Problem Statement
Build a simple SaaS web application for small businesses to automatically send emails in rotation across multiple connected email accounts with daily sending limits.

## Core Requirements
1. **Email Account Management**: Connect multiple email accounts (SMTP/IMAP or OAuth)
2. **List Management**: Upload and manage CSV email lists with multiple lists per user
3. **Campaign Management**: Create campaigns with rich text editor, dynamic variables ({column_name}), save/load campaigns with statuses (Draft, Scheduled, Running, Paused, Paused_daily_limit, Completed, Failed). Pause/Resume functionality for running and scheduled campaigns.
4. **Scheduler**: Schedule campaigns to send at a specific date/time or send immediately
5. **Rotational Sending**: Send emails rotationally across accounts with custom daily limits
6. **Sending Logs**: Detailed logs showing sent/failed status and error messages
7. **Admin Panel**: Platform-wide monitoring for super_admin users
8. **Subscription System**: Stripe-integrated yearly subscriptions with plan limits enforcement
9. **Email Verification**: Mandatory email verification before login (2hr token expiry)
10. **Forgot Password**: Secure password reset with rate limiting
11. **Email Warmup**: Automated warmup system that gradually increases sending volume per account with "(RTM)" subject tag
12. **Drip Campaigns (Sequence-Based)**: Multi-step drip sequences with timezone-aware schedule windows, per-day sending control, randomization, and stop-on-reply / stop-on-bounce rules

## Tech Stack
- **Frontend**: React 19, TailwindCSS, Shadcn UI, Recharts, Framer Motion
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Authentication**: 
  - Emergent-managed Google Social Login
  - Email + Password (bcrypt hashed) with email verification
- **Payments**: Stripe (live keys configured)
- **Transactional Email**: Resend API
- **Live Chat**: Tawk.to (authenticated pages only)

## Database Schema
- **users**: email, name, google_id, password_hash, provider ('google'/'email'), is_active, created_at, role ('user' | 'super_admin'), plan_type ('free'/'starter'/'growth'), subscription_status, stripe_customer_id, stripe_subscription_id, trial_ends_at, billing_cycle_start, billing_cycle_end, grace_period_end, monthly_unique_recipient_count, last_recipient_reset_date, email_verified, verification_token, verification_expires, reset_token, reset_expires
- **user_sessions**: user_id, session_token, expires_at
- **password_reset_attempts**: email, created_at (for rate limiting)
- **email_accounts**: user_id, email, type, credentials (encrypted), daily_limit, daily_sent_count, status
- **email_lists**: user_id, list_name, original_filename, column_headers, total_rows
- **email_list_contacts**: list_id, contact_data, email, status
- **campaigns**: user_id, name, subject, body, status, email_list_id, total_emails, sent_count, scheduled_at
- **email_queue**: campaign_id, recipient_email, status, error_message, sent_at
- **drip_campaigns**: drip_id, user_id, name, from_name, account_ids[], steps[] (each {step_number, subject, body, delay_days, delay_hours}), schedule{timezone, sending_days, start_time, end_time, randomize_time}, stop_on_reply, stop_on_bounce, status (draft/running/paused/completed), total_sent, total_contacts, created_at, updated_at, started_at
- **drip_contacts**: contact_id, drip_id, user_id, email, data (row), current_step, status (active/completed/replied/bounced), next_send_at, enrolled_at
- **drip_logs**: log_id, drip_id, contact_id, contact_email, step, subject, account_email, status (sent/failed/suppressed), error, sent_at
- **dne_lists**: list_id, user_id, name, is_global, email_count, created_at
- **dne_emails**: user_id, list_id, email (lowercase), source (manual/unsubscribe), added_at. Indexes: `(user_id, email)` + unique `(list_id, email)`.

## Pricing Plans (Stripe Integrated)
| Plan | Price (USD/INR) | Accounts | Contacts/Month | Emails/Year |
|------|-----------------|----------|----------------|-------------|
| Free Trial | 14 days | 3 | 500 | - |
| Starter | $99/₹5,000/year | 10 | 4,000 | 48,000 |
| Growth | $149/₹12,000/year | 15 | 10,000 | 120,000 |

### Stripe Price IDs (from environment)
- Starter USD: `price_1T3JubD2HZgi5NSCVPybSMdk`
- Growth USD: `price_1T3Jv7D2HZgi5NSCTvsCbPBi`
- Starter INR: `price_1T3xeED2HZgi5NSCTsHhLaVL`
- Growth INR: `price_1T3xecD2HZgi5NSC84ntUhgG`

## Key API Endpoints
### Authentication
- `/api/auth/session` - Emergent OAuth session exchange (handles Google OAuth callback)
- `/api/auth/register` - Email/Password registration (sets up free trial)
- `/api/auth/login` - Email/Password login
- `/api/auth/me` - Get current user with role and subscription info
- `/api/auth/logout` - Logout

### Subscription (NEW)
- `/api/subscription/prices` - Get plan pricing and limits
- `/api/subscription/status` - Get user's subscription status and usage
- `/api/subscription/create-checkout` - Create Stripe checkout session
- `/api/subscription/create-portal` - Create Stripe billing portal session
- `/api/stripe/webhook` - Handle Stripe webhook events

### Core Features
- `/api/accounts` - Get email accounts with limit info
- `/api/accounts/smtp` - Add SMTP account (enforces plan limits)
- `/api/accounts/{id}/warmup/*` - Warmup enable/disable/pause/resume/settings/stats
- `/api/lists` - Create email list (enforces contact limits)
- `/api/campaigns` - CRUD for campaigns
- `/api/campaigns/{id}/start` - Start campaign immediately
- `/api/campaigns/{id}/schedule` - Schedule campaign for later
- `/api/campaigns/{id}/pause` - Pause running campaign
- `/api/campaigns/{id}/resume` - Resume paused campaign
- `/api/campaigns/{id}/logs` - Sending logs

### Drip Campaigns (Feb 2026 — NEW)
- `GET /api/drip-campaigns` - List user's drip campaigns
- `POST /api/drip-campaigns` - Create new drip (draft)
- `GET /api/drip-campaigns/{drip_id}` - Get campaign with live stats
- `PUT /api/drip-campaigns/{drip_id}` - Update drip (draft/paused only)
- `DELETE /api/drip-campaigns/{drip_id}` - Delete drip + its contacts + logs
- `POST /api/drip-campaigns/{drip_id}/contacts` - Enroll contacts from a list
- `GET /api/drip-campaigns/{drip_id}/contacts` - Paginated enrolled contacts
- `GET /api/drip-campaigns/{drip_id}/logs` - Send logs
- `GET /api/drip-campaigns/{drip_id}/logs/export` - CSV export
- `POST /api/drip-campaigns/{drip_id}/start|pause|resume` - State transitions

### Admin
- `/api/admin/stats` & `/api/admin/users` - Admin endpoints (super_admin only)

## User Roles
- **user**: Standard access to dashboard, campaigns, email accounts, lists
- **super_admin**: Full access + admin panel (dhruvmathur208@gmail.com)

---

## Implementation Status

### ✅ Manual records, explicit DNE, in-editor unsubscribe link, no daily cap, searchable account picker (Feb 2026)
- [x] **Manual Add/Delete records in lists** — `POST /api/lists/{id}/records` (validated email, lowercased, trimmed, dedupe per-list) + `DELETE /api/lists/{id}/records`. Frontend: Add Record dialog + per-row trash with confirmation in ListDetails.
- [x] **Global DNE no longer auto-applied** — `is_email_suppressed` only checks DNE lists explicitly attached to the campaign; the legacy `suppression_list` (the unsubscribe register) remains the authoritative permanent block and is ALWAYS checked. Campaign + Drip Settings now show all DNE lists (Global as a regular checkbox with badge), with a warning banner when none selected.
- [x] **In-editor "Add Unsubscribe Link"** — new toolbar button in shared RichTextEditor inserts `<a href="{{unsubscribe_url}}">…</a>` with editable link text. Backend resolves the placeholder to per-recipient `/api/unsubscribe/{user_id}/{email}` at send-time for both standard campaigns AND drip steps. Default footer is suppressed when the body already contains the URL (URL-match only, link text agnostic).
- [x] **Unsubscribe immediately stops drips** — `/api/unsubscribe` now writes to suppression_list + Global DNE AND `update_many`-marks any active drip_contacts as `unsubscribed` for that email + user.
- [x] **No daily-limit cap** — backend min=1, no max. Frontend min=1, no max. "Recommended maximum: 50 emails per day for better deliverability" helper text in Add + Edit dialogs.
- [x] **Searchable account multi-select** — new `AccountMultiSelect` (shadcn Popover + checkboxes) used in Campaign and Drip Settings; search by email or display_name; Select-All / Clear-Selection; internal scroll; compact "X selected" trigger summary. Empty selection still uses all connected accounts.
- [x] Tested: 19/19 new backend + 47/47 regression (iteration_28). Source-level verification on all 9 new frontend testids.

### ✅ Drip RTE + Auto-resume after daily limit (Feb 2026)
- [x] **Drip step body uses shared RichTextEditor** — same component (`/app/frontend/src/components/RichTextEditor.jsx`) as standard campaigns. Bold/italic/underline, alignment, lists, links, images, variable insertion, plain-text toggle. HTML round-trips through PUT `/api/drip-campaigns/{id}` and renders correctly via `send_drip_email` (which already attaches both text + HTML MIME parts).
- [x] **Auto-resume daily-limit-paused campaigns** — `check_scheduled_campaigns` scheduler loop (every 30s) now also enumerates `status='paused_daily_limit'` campaigns and flips them back to `running` (+ records `auto_resumed_at`) once at least one of their accounts has rolled over to a new day OR has fresh quota (e.g. user raised the limit). It then re-spawns `process_campaign_queue` to resume from the next `pending` queue item — no duplicates.
- [x] User-paused campaigns (`status='paused'`) are NOT touched by the auto-resume loop.
- [x] Drip campaigns already auto-retry per-cycle (60s loop) — verified contact `current_step` stays unchanged when accounts hit limit, advances normally after rollover.
- [x] UI labels updated to communicate auto-resume behaviour ("Daily limit reached — will resume automatically").
- [x] Tested: 5/5 new backend tests + 47/47 regression (iteration_27).

### ✅ Usability pass (Feb 2026)
- [x] **Edit list records** — per-row edit dialog in ListDetails; PUT `/api/lists/{list_id}/record` validates email + checks collisions, preserves custom columns
- [x] **Download email list as CSV** — GET `/api/lists/{list_id}/export` streams CSV with `email` first + all custom columns; icon on list cards + detail page
- [x] **Bulk import SMTP accounts** — `POST /api/accounts/smtp/bulk-import` (CSV only, ≤1MB, ≤200 rows), per-row results, duplicates skipped, delay defaults to 30s, daily_limit defaults to 50; `GET /api/accounts/smtp/sample-csv` for the sample download
- [x] **View / Edit SMTP account** — `GET /api/accounts/{id}` (password blob excluded server-side), `PUT /api/accounts/{id}` (password is optional — only sent if user rotates it; SMTP re-test runs only when credentials/host/port/username/encryption actually change)
- [x] **Scrollable body editor** — RichTextEditor now has `min-h-[300px] max-h-[400px] overflow-y-auto` (HTML + plain-text modes)
- [x] **Timezone bug fixed** — frontend sends NAIVE local datetime + `timezone` name; new server helper `parse_scheduled_at_in_timezone` localises via pytz → UTC; existing offset/Z strings still honoured. Displayed back to user in stored timezone.
- [x] **Independent scroll for Email Accounts list** — wrapper `data-testid="email-accounts-list"` with `max-height: calc(100vh - 260px)` + `overflow-y: auto`
- [x] Tested: 28/28 new backend + 47/47 regression (iteration_26). Password-blob never exposed in account GET.

### ✅ Do Not Email (Suppression) System (Feb 2026)
- [x] New collections: `dne_lists`, `dne_emails` (indexed `user_id+email` + unique `list_id+email`)
- [x] Schema extended: `campaigns.suppression_list_ids`, `drip_campaigns.suppression_list_ids`, new queue status `suppressed`, new drip contact/log status `suppressed`
- [x] Backend CRUD: `/api/dne-lists` list/create/delete, `/api/dne-lists/{id}` get/delete, `/api/dne-lists/{id}/emails` add/remove, `/api/dne-lists/{id}/upload` (CSV+XLSX, 2MB cap, dedupe+normalize+validate)
- [x] Global DNE list auto-created per user (lazy), cannot be deleted
- [x] Real-time suppression in standard campaign sender (`process_campaign_queue`) — flags queue item as `suppressed`, never sends
- [x] Real-time suppression in drip worker (`process_drip_contact`) — checked before every step; contact flipped to `status=suppressed`, log entry written
- [x] Unsubscribe link (`GET /api/unsubscribe/...`) and `POST /api/suppression` both auto-mirror into user's Global DNE list
- [x] Referential cleanup: deleting a DNE list auto-unlinks it via `$pull` from referencing campaigns + drip_campaigns
- [x] Frontend: sidebar "Do Not Email" entry (ShieldOff icon), `/do-not-email` + `/do-not-email/:listId` pages with CSV/XLSX upload, bulk paste, search, pagination, delete
- [x] Campaign form + Drip Settings tab: multi-select DNE list checkboxes with helper text; Global always-applied banner
- [x] Logs: new "Suppressed" filter + badge in CampaignLogs; rose-colored "Suppressed" stat in drip detail
- [x] Tested: 24/24 DNE backend tests + 23/23 drip regression (iteration_25), no failures

### ✅ Drip Campaigns — Sequence-Based Campaigns (Feb 2026)
- [x] Backend Pydantic models: `DripStep`, `DripScheduleSettings`, `CreateDripCampaignRequest`, `UpdateDripCampaignRequest`, `AddDripContactsRequest`
- [x] Full CRUD + control API (`/api/drip-campaigns` …/contacts, /logs, /logs/export, /start, /pause, /resume)
- [x] Ownership guards, 400 state-guards (edit/delete rejected while running; start requires steps+accounts+contacts)
- [x] Frontend `/drip-campaigns` list page with create dialog and card grid
- [x] Frontend `/drip-campaigns/:dripId` detail page with tabs: Sequence, Schedule, Contacts, Logs, Settings
- [x] Timezone-aware schedule (timezone, sending days, start/end window, randomize)
- [x] Stop-on-reply / stop-on-bounce toggles
- [x] Per-step delay (days + hours), inline editor with `{column_name}` merge hints
- [x] Enroll contacts from an existing email list with duplicate skipping
- [x] CSV export of send logs
- [x] Sidebar link "Drip Campaigns" (Workflow icon)
- [x] `pytz` added to requirements.txt
- [x] Tested: 23/23 backend tests + all targeted frontend flows (iteration_24)

### ✅ Completed Features
- [x] User authentication with Google OAuth (Emergent-managed)
- [x] Email + Password authentication (bcrypt hashed)
- [x] Role-based access control (user/super_admin)
- [x] Multi-list management system with CSV upload
- [x] Campaign creation with rich text editor
- [x] Campaign scheduler (Send Now / Schedule for Later)
- [x] SMTP email account connection
- [x] Analytics-style user dashboard with charts
- [x] Super Admin panel with stats and user management
- [x] Campaign logs page
- [x] Modern public landing page with animations
- [x] Protected routes for admin section
- [x] Tawk.to live chat widget (authenticated pages only)

### ✅ Auth + Branding Updates (Dec 2025)
- [x] Email + Password registration with validation
- [x] Email + Password login (separate from Google)
- [x] Login page (/login) with dual auth options
- [x] Register page (/register) with password strength indicator
- [x] Branding updated to "RoutEmail"
- [x] Tagline: "Send Bulk Emails Safely from Multiple Accounts."
- [x] Footer contact: support@routemail.co
- [x] Tawk.to integration for authenticated pages only

### ✅ Bug Fixes (Dec 2025)
- [x] Google OAuth "Not Found" Error - Fixed redirect URL to use Emergent Auth directly

### ✅ Stripe Subscription System (Dec 2025)
- [x] Stripe integration with live keys
- [x] Yearly subscription plans (Starter/Growth)
- [x] Geo-based pricing (USD for most countries, INR for India)
- [x] Stripe Checkout Session creation
- [x] Webhook handlers (checkout.session.completed, invoice.paid, invoice.payment_failed, customer.subscription.deleted, customer.subscription.updated)
- [x] Free 14-day trial on registration
- [x] Plan limits enforcement (accounts, contacts, monthly recipients)
- [x] Subscription management page with usage stats
- [x] Grace period handling for failed payments (7 days)
- [x] Logo resized to ~100px on landing page navbar

### ✅ Upgrade Flow & Dashboard Improvements (Dec 2025)
- [x] Dashboard upgrade banner for free users (shows trial days remaining)
- [x] Plan & Usage card on dashboard (current plan, usage stats, limits)
- [x] Landing page pricing buttons pass plan in query params (/register?plan=starter)
- [x] Register page auto-redirects to Stripe checkout after registration if paid plan selected
- [x] Selected plan banner on registration page
- [x] Subscription page shows status badges, trial days, billing dates
- [x] Alert banners for expired trials, past due payments, scheduled downgrades

### ✅ Pricing Fixes & UX Improvements (Dec 2025)
- [x] Removed "Book a Demo" CTA from hero and final sections
- [x] Fixed INR pricing: Starter ₹5,000/year, Growth ₹12,000/year
- [x] Removed currency toggle - uses automatic geo-based detection
- [x] Added "Back to Dashboard" button on subscription page
- [x] Added Logout button in dashboard header
- [x] Implemented first-time user onboarding tour (4 steps: Accounts, Lists, Campaign, Subscription)
- [x] Onboarding persists in localStorage to prevent re-showing

### ✅ Dashboard UI Improvements & Plan Visibility (Feb 2026)
- [x] Upgrade banner shows specific plan options (Free → Starter/Growth, Starter → Growth)
- [x] "Quick Start" renamed to "Start Your Campaigns" with darker background, border, and shadow
- [x] "Connect Accounts" renamed to "Connect Email Accounts"
- [x] CTA buttons (Add Accounts, Upload List, Create Campaign) have filled backgrounds with strong visual weight
- [x] Added "How to Launch Your First Campaign" instruction steps (4 steps with colored icons)
- [x] "Create Campaign" button always visible (even if accounts/lists not set up)
- [x] Campaign page shows warning banner if user hasn't set up accounts/lists
- [x] Subscription page shows correct upgrade/downgrade/cancel buttons based on current plan
- [x] Sidebar displays dynamic plan badge (Free/Starter/Growth) from user's actual subscription
- [x] Logo in sidebar/mobile header is now clickable and redirects to dashboard
- [x] Fixed accounts API response handling (accounts.map error)

### ✅ Permanent Plan Assignments & Sidebar Fix (Feb 2026)
- [x] Permanent plan assignments configured for specific accounts (bypasses Stripe):
  - `dhruvmathur5@gmail.com` → Starter Plan (10 accounts, 4,000 contacts, 4,000 recipients/month)
  - `perfectdigitals208@gmail.com` → Growth Plan (15 accounts, 10,000 contacts, 10,000 recipients/month)
- [x] Fixed sidebar not rendering on desktop (replaced framer motion with CSS transitions)
- [x] Logo visible consistently across ALL dashboard pages (~80px height)
- [x] Sidebar visible on: Dashboard, Email Accounts, Email Lists, Campaign, Subscription pages
- [x] Logo is clickable and navigates to /dashboard

### ✅ Major Platform Update (Feb 2026)
- [x] **Rebranding**: "RoutEmail" → "RouteMail" across all UI, emails, meta tags
- [x] **New Logo**: Updated logo displayed across landing, auth, and dashboard pages
- [x] **Meta Title**: "RouteMail | Bulk Email Sending Platform for SME"
- [x] **Footer Credit**: "Developed by Perfect Digitals" with link to perfectdigitals.ie
- [x] **Authentication System (Resend Integration)**:
  - Email verification on registration (2hr token expiry)
  - Verification email with branded HTML template
  - Welcome emails based on plan type (Free/Starter/Growth)
  - Forgot password with 30-min token, 3 attempts/hour rate limit
  - Password reset flow with secure token validation
  - New pages: /verify-email, /forgot-password, /reset-password
- [x] **Pricing Updates**:
  - Starter: 4,000 contacts/month, 48,000 emails/year, Unlimited emails
  - Growth: 10,000 contacts/month, 120,000 emails/year, Unlimited emails
- [x] **File Upload**: 2MB max file size for CSV uploads

### ✅ Rich Text Editor & Campaign Page Improvements (Feb 2026)
- [x] **Enhanced Rich Text Editor**:
  - Font Size selector (dropdown: Small, Normal, Large, Extra Large)
  - Font Color picker with preset colors + custom color picker
  - Text alignment (left, center, right)
  - Bold / Italic / Underline buttons
  - Bullet & numbered lists
  - Hyperlink insert with popover dialog
  - Image upload & insert support (base64, max 2MB)
- [x] **Campaign Page Layout Reorganized**:
  - Campaign Name
  - From Name (optional)
  - Select Email Accounts (checkboxes)
  - Select Email List
  - Subject Line
  - Email Body (Rich Text Editor)
  - Save Draft button (below editor)
  - Send Test Email button (below editor)
  - Send Now / Schedule Later options
  - Start Campaign button (at bottom)
- [x] **Send Test Email Feature**:
  - Opens modal dialog for test email input
  - Sends preview with [TEST] prefix in subject
  - Does not affect campaign stats or logs
  - Validates: subject, body, connected accounts

### ✅ Bug Fixes & Legal Pages (Feb 2026)
- [x] **Fixed "Send Test Email" Not Working**:
  - Bug: "Failed to decrypt account credentials" error
  - Root cause: Backend checking for `smtp_password` field but DB uses `smtp_password_encrypted`
  - Fix: Updated server.py lines 1771, 1780 to use correct field name
- [x] **Fixed Email Activation "Failed" Message Bug**:
  - Bug: UI showing "Activation Failed" before immediately showing success
  - Root cause: Race condition in React useEffect with StrictMode
  - Fix: Added `verificationCompleted` ref + handled "already verified" case gracefully
- [x] **Added Legal Pages**:
  - /privacy-policy - Full Privacy Policy with GDPR compliance
  - /terms-and-conditions - Terms and Conditions with No Refund Policy
  - /anti-spam-policy - Zero-tolerance spam policy with prohibited content
  - /gdpr-compliance - EU GDPR compliance information
- [x] **Footer Links**: All 4 legal page links added to landing page footer

### ✅ Major Feature Fixes (March 2026)
- [x] **Hyperlink Fix**: Links now properly wrap text and images with `<a href="..." target="_blank">` tags
- [x] **Variable Insertion Fix**: Variables now insert at cursor position using savedRange ref
- [x] **Send Now Fix**: Immediately starts campaign and redirects to Dashboard with success toast
- [x] **Timezone Selector**: Added 16 timezone options to scheduling UI, stored with campaign
- [x] **Test Email Account Selection**: Dropdown to choose which connected account to use
- [x] **Test Email Response Fix**: Proper success/error handling with clear messages
- [x] **Campaign View Page**: New page at `/campaign/:id/view` showing full campaign details (read-only)

### ✅ New Features (Feb 2026)
- [x] **Word-Style Image Resize in Campaign Editor**:
  - Click image to select (blue outline)
  - 4 corner drag handles for resize
  - Maintains aspect ratio during resize
  - Stores width attribute for email client compatibility
  - Max 600px on upload for email compatibility
- [x] **Super Admin Force Password Reset**:
  - New endpoint: `/api/admin/users/{user_id}/force-password-reset`
  - KeyRound icon button in admin panel user table
  - Confirmation dialog with amber styling
  - Uses routemail.co domain for reset links
  - 1 hour token expiry
  - Logs admin actions to `admin_logs` collection
  - Cannot reset OAuth users (returns error)

### ✅ Production Auth Fixes (Feb 2026)
- [x] **Registration "Failed" False Error Fixed**:
  - Changed registration endpoint to return HTTP 201 status explicitly
  - Improved frontend error handling to distinguish network errors from server errors
  - Registration now correctly shows success screen
- [x] **Email Link Domain Fixed**:
  - All verification links: `https://routemail.co/verify-email?token=...`
  - All password reset links: `https://routemail.co/reset-password?token=...`
  - Post-verification redirect: `https://routemail.co/dashboard`
  - Added logging for all link generation
- [x] **FRONTEND_URL Configuration**: Set to `https://routemail.co` in backend/.env

### ✅ Minor Updates (Feb 2026)
- [x] **Privacy Policy Text Updated**: Company info changed to "Registered in India / RouteMail / Perfect Multimedia / 1036C B3 Tower Spaze iTech Park, Gurgaon, Haryana 122018"
- [x] **Hero Heading Updated**: Removed period from "from Multiple Accounts."
- [x] **Onboarding Popups Fix**: Changed from localStorage to database-backed (`onboarding_completed` field in users collection). Now shows only on first login, persists across sessions and devices.
- [x] **Email Verification Redirect Fix**: 
  - Backend returns `redirect_url` based on `FRONTEND_URL` env var
  - Frontend uses `window.location.href` for absolute redirect to production domain
  - On success → redirects to `{FRONTEND_URL}/dashboard` (https://routemail.co/dashboard in production)
  - Fixed error message parsing to correctly distinguish "invalid" vs "expired" tokens
- [x] **Registration & Verification Flow Hardening**:
  - Added try/catch around user creation with proper error handling
  - Added logging for user creation and email verification
  - Made token update atomic to prevent race conditions
  - Added `onboarding_completed: False` to new user documents
- [x] **Production FRONTEND_URL Fix**:
  - Updated `FRONTEND_URL` in backend/.env from preview domain to `https://routemail.co`
  - All email links (verification, password reset, Stripe) now use production domain

### ✅ Scheduled Campaign Background Worker (March 2026)
- [x] **Background Scheduler Implementation**:
  - Async background task runs every 30 seconds
  - Checks for campaigns with `status: "scheduled"` and `scheduled_at` in the past
  - Automatically starts campaigns when scheduled time arrives
  - Creates email queue items with correct `queue_id` field
  - Transitions campaign status: `scheduled` → `running` → `completed`
  - Proper error handling with status set to `failed` if issues occur
  - Graceful startup/shutdown with asyncio task management
- [x] **Bug Fix**: Fixed queue item field name from `queue_item_id` to `queue_id` (matching model and processing code)
- [x] **Endpoints Working**:
  - `POST /api/campaigns/{id}/schedule` - Sets status to `scheduled`
  - `POST /api/campaigns/{id}/unschedule` - Returns to `draft` status
  - Campaign creation with `scheduled_at` auto-sets status to `scheduled`

### ✅ Super Admin Subscription Details (March 2026)
- [x] **New Admin Endpoint**: `GET /api/admin/users/{user_id}/subscription`
  - Returns detailed subscription info for any user (super_admin only)
  - Combines local MongoDB data with Stripe API data
  - Handles Stripe API failures gracefully (shows local data)
  - Logs admin actions to `admin_logs` collection
- [x] **Subscription Details Modal** in Admin Panel:
  - CreditCard icon button in each user row
  - Displays: Current Plan, Currency, Billing Status, Stripe IDs
  - Shows: Trial Active (Yes/No), Trial End Date, Subscription End Date
  - Special handling for permanent plan users (shows badge + notes)
- [x] **Edge Cases Handled**:
  - Free plan users: Currency=N/A, Stripe IDs=N/A
  - Permanent plan users: billing_status=permanent, notes displayed
  - Trialing users: trial_active=true with end date

### ✅ Campaign & Email Account Improvements (March 2026)
- [x] **Hyperlink Fix Enhanced**: 
  - Selected text now properly wrapped in `<a href="..." target="_blank" rel="noopener noreferrer">` tags
  - Uses `range.extractContents()` to correctly wrap selected content
  - Restores cursor position from `savedRange` before insertion
- [x] **Campaign Page Button Improvements**:
  - "Save Draft" renamed to "Save Campaign" - saves campaign as draft
  - Merged "Start Campaign" into single primary CTA
  - Shows "Send Now" when immediate send option selected
  - Shows "Schedule Now" when schedule option selected
- [x] **Add New List Option**:
  - Added "➕ Add New List" option at bottom of list dropdown
  - Auto-saves current campaign as draft before redirecting
  - Stores `returnToCampaign` in sessionStorage for return navigation
- [x] **Campaign View Page Enhanced**: 
  - `/campaign/:campaignId/view` shows full campaign details
  - Displays: name, subject, body (rendered HTML), status, stats
  - Shows: selected accounts, selected list, from_name, timezone
  - Read-only view for sent/completed campaigns
- [x] **Send Delay Configuration**:
  - New `send_delay` field on email accounts (10-300 seconds, default 30)
  - `PUT /api/accounts/{id}/delay` endpoint to update delay
  - Frontend UI in add account dialog and account card editor
  - Sending logic uses account's `send_delay` with ±2s randomization

### ✅ Excel Upload & Pricing Updates (March 2026)
- [x] **Excel File Upload Support**:
  - Backend now accepts `.csv`, `.xlsx`, and `.xls` files
  - Uses pandas with openpyxl (for .xlsx) and xlrd (for .xls) engines
  - First row treated as column headers (same as CSV)
  - Email column validation remains enforced
  - 2MB file size limit maintained
  - Variables from columns work identically to CSV
- [x] **Pricing Text Updates**:
  - Free Plan: Changed "500 stored contacts" to "500 contacts/month"
  - Removed duplicate "500 recipients/month" line from Free plan
  - Starter Plan: Changed "48,000 emails per year" to "48,000 contacts per year"
  - Growth Plan: Changed "120,000 emails per year" to "120,000 contacts per year"
- [x] **"/year" Visual Enhancement**:
  - Price suffix now uses `text-xl font-medium` styling
  - More prominent display on both Landing and Subscription pages
  - Consistent across all paid plans

### ✅ Admin Plan Override System (March 2026)
- [x] **New Database Fields**:
  - `admin_override_active` (boolean) - whether admin override is active
  - `admin_override_plan` (string) - "starter" or "growth"
  - `plan_source` (string) - "free", "stripe", or "admin_override"
  - `admin_override_updated_at` (datetime) - when override was last changed
- [x] **Plan Resolution Priority**:
  1. Admin override (if `admin_override_active = true`)
  2. Stripe subscription (if `stripe_subscription_id` exists)
  3. Free plan (default)
- [x] **Helper Function**: `get_effective_user_plan()` - centralized plan resolution
- [x] **Backend Endpoints**:
  - `POST /api/admin/users/{id}/assign-plan` - Assign Starter or Growth plan
  - `POST /api/admin/users/{id}/remove-override` - Remove override, revert to Free
- [x] **Security**:
  - Only super_admin can use override endpoints
  - Blocked for users with active Stripe subscriptions
  - Blocked for permanent plan users
  - All actions logged to `admin_logs` collection
- [x] **Frontend Plan Override Modal**:
  - UserCog icon button in admin user table
  - Shows current plan and plan source
  - "Admin Override Active" badge when override is active
  - Assign Starter/Growth buttons (disabled for Stripe users)
  - Remove Override button with confirmation dialog
  - Warning message for Stripe and permanent plan users

### ✅ Reset Password Fix (March 2026)
- [x] **SPA Routing Configuration Added**:
  - `/app/frontend/public/_redirects` - For Netlify and general hosting
  - `/app/frontend/vercel.json` - For Vercel hosting
  - `/app/frontend/public/staticwebapp.config.json` - For Azure Static Web Apps
- [x] **Backend URL Generation Verified**:
  - FRONTEND_URL correctly set to `https://routemail.co`
  - Reset links generated as: `https://routemail.co/reset-password?token=...`
- [x] **Reset Password Flow Tested**:
  - `POST /api/auth/forgot-password` - Sends email with correct link
  - `POST /api/auth/reset-password` - Validates token, updates password
  - Frontend ResetPassword.jsx - Shows form with token, error without
  - Token expiry (30 minutes) handled correctly
- [x] **Note**: Production fix requires deployment with SPA routing config

### ✅ Admin Notifications & Signup Improvements (March 2026)
- [x] **FRONTEND_URL Trailing Slash Fix**:
  - Added `.rstrip('/')` to prevent double slashes in URLs
  - Fixes `routemail.co//reset-password` → `routemail.co/reset-password`
- [x] **Admin Notification Emails** (to support@routemail.co):
  - New user signup (Email + Password): background task in registration
  - New user signup (Google OAuth): asyncio task on first session
  - Paid subscription: triggered on `checkout.session.completed` webhook
  - All notifications are fail-safe (logged errors, don't interrupt user flow)
- [x] **Footer Cleanup**:
  - Removed "Developed by Perfect Digitals" text and link from landing page
- [x] **Terms & Privacy Acceptance Required for Signup**:
  - Checkbox with links to `/terms-and-conditions` and `/privacy-policy`
  - Mandatory for both email and Google signup
  - Error message: "You must accept the Terms and Conditions and Privacy Policy"
  - Validated client-side before API calls

### ✅ Landing Page Visual Enhancements (March 2026)
- [x] **Added Professional Images** to 4 sections:
  - "Why This Tool Exists": Bulk email professional image (left/top on mobile)
  - "How It Works": Email icon image (centered below title)
  - "What Makes It Different": Smartphone campaign control image (left side)
  - "Use Cases": Laptop typing productivity image (right side)
- [x] **Image Styling Applied**:
  - border-radius: 16px
  - box-shadow: 0 10px 25px rgba(0,0,0,0.08)
  - max-width constraints (280px-450px depending on section)
  - height: auto for aspect ratio preservation
- [x] **Performance Optimizations**:
  - lazy loading enabled on all images
  - Fade-in animations using Framer Motion
  - Responsive layouts with mobile-first approach

### ✅ System Email Branding & Signup UX (March 2026)
- [x] **RouteMail Logo Added to All System Emails**:
  - Verification email - Centered logo at top (160px width)
  - Password reset email - Centered logo at top
  - Welcome email (Free/Starter/Growth) - Centered logo at top
  - Admin signup notification - Centered logo at top
  - Admin subscription notification - Centered logo at top
- [x] **Email Template Improvements**:
  - Consistent max-width: 600px container across all emails
  - Arial font-family for email client compatibility
  - Inline CSS styling for cross-client support (Gmail, Outlook, Apple Mail)
  - Logo URL: `https://routemail.co/routemail-logo.png`
  - All templates maintain brand gradient colors for CTAs
- [x] **Signup Confirmation UI Enhanced**:
  - Green success alert box: "Verification Link Sent!"
  - Clear message: "Please check your email to verify your account."
  - Amber warning box with spam/junk folder reminder
  - User's registered email displayed prominently
  - Resend Verification Email button
  - Use Different Email button to restart
  - Animated checkmark icon on success screen

### ✅ Final Batch — Blog, Tawk removal, Send Range, Dashboard UI (Feb 2026)
- [x] **Public Blog with Super Admin management** — `POST/PUT/DELETE /api/blogs[/{id}]` (super-admin only), `GET /api/blogs` + `GET /api/blogs/{slug}` public; admin Featured-image upload (base64). Frontend: `/blog`, `/blog/:slug`, `/admin/blogs`.
- [x] **Tawk chat widget removed** — `TawkWidget.jsx` deleted, App.js cleaned. No `embed.tawk.to` on any page.
- [x] **Show current SMTP password on edit** — `GET /api/accounts/{id}/credential` (owner-scoped) + reveal toggle in EmailAccounts edit dialog.
- [x] **Daily limit text** — "Recommended maximum: 50 emails per day for better deliverability" (min=1, no max).
- [x] **Send Range on Standard Campaigns** — `send_range_mode` ('all'|'range') + 1-based `send_range_start`/`send_range_end`. Applied at `/start` and in scheduled-campaign worker. UI in Campaign.jsx between list select and subject (`data-testid="send-range-section"`).
- [x] **Send Range on Drip Campaigns** — `AddDripContactsRequest` extended with `send_range_mode/start/end`; slicing applied before `drip_contacts.insert_many`. UI in DripCampaignView "Add contacts" dialog (`drip-send-range-section`, `drip-send-range-all-radio`, `drip-send-range-range-radio`, `drip-send-range-start-input`, `drip-send-range-end-input`).
- [x] **Dashboard Campaign Activity in first fold** — moved above metric cards in Dashboard.jsx; `slice(0, 4)`; "View All" CTA → `/campaign`. Testids: `campaign-activity-section`, `campaign-activity-view-all-btn`, `campaign-activity-row-{id}`.
- [x] Tested: 12/12 new backend + 66/66 regression (iteration_29). Frontend Playwright: Dashboard first-fold + 4 rows + View All verified. Drip Send Range dialog interactively verified by main agent (section + radios + From/To inputs render correctly).

### ✅ Upload Limits Relaxed (Feb 2026)
- [x] **Email list upload (`/api/lists/upload`)** — removed the 2MB cap completely. CSV/XLSX/XLS uploads of any reasonable size now process. Verified 5.28 MB CSV with 180,000 rows imports in seconds; 3.9 MB / 80,000 rows also OK. Existing validation (email column, duplicates, normalization) preserved.
- [x] **UploadList.jsx UX** — added axios `onUploadProgress` (shows "Uploading X%" on the Select File button), and a `toast.loading` for files >2MB so the user sees a "Uploading X MB — N%" indicator until the server finishes parsing. Existing "Processing…" state preserved as fallback.
- [x] **RichTextEditor image upload** — bumped from 2MB to 5MB and tightened allowed types to JPG/PNG/WEBP/GIF only. Used by Campaign editor and Drip campaign editor (shared component). Error text: "Image size exceeds maximum allowed size of 5 MB".
- [x] **Blog featured image (`/api/admin/blogs/upload-image`)** — bumped from 3MB to 5MB with the same error text.
- [x] DNE list upload (`/api/dne-lists/{id}/upload`) intentionally LEFT untouched — out of scope.

### ✅ Multi-Feature Batch — Capacity, Headers, Test Mail, Drip UX, Auto-save, Heading Colors (Feb 2026)
- [x] **Total Daily Sending Capacity** indicator on Campaign + Drip account selectors — sums `daily_limit` across selected accounts (or all connected when nothing picked). Live updates as selection changes. Testids `total-daily-capacity`, `drip-total-daily-capacity`. Hidden when there are 0 connected accounts.
- [x] **Header normalization** in `/api/lists/upload` — lowercase, replaces spaces/dots/dashes with `_`, strips other special chars, dedupes with `_2/_3` suffixes. Verified `['Email','First Name','first-name','Company.Name!','Last  Name'] → ['email','first_name','first_name_2','company_name','last_name']`.
- [x] **Test Mail with selected contact** — Campaign + Drip per-step Test dialogs now have a "Personalize with contact" picker pulled from the selected list. `SendTestEmailRequest.recipient_data` field added; backend runs `replace_variables(...)` on subject and body when provided.
- [x] **Drip per-step Test Mail** — buttons `drip-step-{idx}-test-btn` open a dialog with account/email/list/recipient pickers and call the same `/api/campaigns/send-test` endpoint (test mails do NOT count toward sending limits or update stats).
- [x] **Drip tabs reordered** to **Select List → Settings → Sequence → Schedule → Logs**. Default open tab is now `Select List`.
- [x] **Drip Duplicate Step** — `Copy` button per step inserts a new step right after the source with the same subject/body and renumbered `step_number`. Verified live.
- [x] **Auto-save draft on Back** — `Campaign.jsx` `back-btn` and `DripCampaignView.jsx` `drip-back-btn` silently PUT/POST the form when there's enough content; toast shows `Draft saved automatically`.
- [x] **Send Now / Schedule Now auto-save first** — `handleSendNow` PUTs (or creates) the campaign before starting; both flows redirect to `/campaign` (All Campaigns).
- [x] **Heading accent colors** — Campaign setup labels use distinct colors (violet/indigo/blue/rose/emerald/cyan/amber) for visual hierarchy without clutter.
- [x] **Open/Click tracking** — INTENTIONALLY SKIPPED per user choice (option `c`).
- [x] Tested: 11/11 new backend + 59/59 regression (iteration_30). Drip step duplicate, tab order, accent colors, back-btn, drip-step-test-dialog all verified live.

### ✅ 15-Feature Batch — Drip UX, Subscription overhaul, Custom Plan, Admin Overrides (Feb 2026)
- [x] **Drip tabs UI** — rounded pill buttons with per-tab accent (emerald/amber/violet/blue/slate), active state has white bg + ring + shadow, hover transitions; default opens "Select List".
- [x] **"Sequence" → "Compose Emails"** — tab label, header subtitle, and section heading all renamed.
- [x] **Unsubscribe footer OFF by default** — backend `Campaign.add_unsubscribe_footer` (default False); `send_email_smtp(...)` only appends the default footer when True. Per-campaign opt-in toggle in Campaign.jsx Settings (`add-unsubscribe-footer-toggle`). Manual `{{unsubscribe_url}}` insertion via the editor still works.
- [x] **Drip start validation** — `validateDripBeforeStart()` blocks Start unless name + ≥1 connected account + enrolled contacts + ≥1 step with subject+body; auto-saves before starting; toasts the missing field and switches to the relevant tab.
- [x] **Scrollable contacts list** — `drip-contacts-scroll` wrapper, max-height 250px, sticky header, overflow-y auto.
- [x] **Auto-hyperlink in RichTextEditor** — `autoLinkText()` covers URLs, `www.`, and emails; runs on paste (insertHTML) and on blur (TreeWalker over text nodes, skips text already inside `<a>`).
- [x] **Cancel/Downgrade buttons removed** — Subscription page now shows a friendly "email support@routemail.co" note in every plan card + a global note at the bottom.
- [x] **Email Lists contact-count badge** — `list-contacts-badge-{id}` with formatted `valid_emails` per row.
- [x] **Subscription logic clarified** — pricing already keyed off unique recipients/month; UI now puts a prominent "Contacts Used This Month" tracker (current/limit + progress bar + remaining + 0/80/95% color tiers) at the top of the page.
- [x] **Custom Plan slabs** — 6 tiers (15k/$199, 20k/$249, 30k/$349, 50k/$499, 75k/$699, 100k/$899/yr). Stripe Price IDs set in env: `STRIPE_PRICE_CUSTOM_15K..100K`. Subscription card has a slab grid + dynamic upgrade button → `/api/subscription/create-checkout`. Backend `PLAN_LIMITS` includes all 6 slabs (max_accounts=25 by default, max_contacts=slab size).
- [x] **Super-admin per-user limit overrides** — new `POST /api/admin/users/{id}/limit-override` (super-admin gated) sets `admin_override_max_accounts` and `admin_override_max_contacts`. `get_user_plan_limits()` applies these on top of plan limits. AdminDashboard exposes `manual-limit-overrides` form with save + clear actions, doesn't touch Stripe.
- [x] **Open/Click tracking** — INTENTIONALLY SKIPPED per user choice (option `c`).
- [x] Tested: pytest **20/20 PASSED** for new features (incl. add_unsubscribe_footer persistence after fix), 58/58 regression on iteration_30/drip/dne. Frontend Playwright: subscription card grid, monthly tracker, all forbidden testids absent (cancel-/downgrade-*).

### ✅ Landing Page + Subscription UI Redesign (Feb 2026)
- [x] **LandingPage** fully rewritten — sticky glassmorphism header, hero with dashboard mockup + floating stat cards, trust strip (12M+/98.4%/1.5k+/47), Interactive Demo with 5 tabs (Dashboard / Campaign Builder / Drip / Warmup / Analytics) all framer-motion AnimatePresence with zero API calls, 5 alternating feature sections each with stylized HTML mockup, 5-persona Use Cases grid, refreshed Pricing (Starter / Growth featured / Custom), Why RouteMail, FAQ accordion (5), CTA banner, footer with policy links + `support@routemail.co`. **Removed "Developed by Perfect Digitals" everywhere.**
- [x] **Shared CustomPlanCard component** — `/app/frontend/src/components/CustomPlanCard.jsx`, two variants:
  - `public` (landing) → CTA routes to `/register?plan=<slug>`
  - `dashboard` (Subscription page) → CTA fires `/api/subscription/create-checkout` with the matching Stripe price_id
  - Pulls slabs from `/api/subscription/prices` with a static fallback. Dropdown updates `custom-plan-price` live.
- [x] **Subscription page** simplified — replaced the inline 6-slab grid with `<CustomPlanCard variant="dashboard" />`. Existing tracker, current-plan banner, support note kept as-is.
- [x] **Pricing copy** — only based on monthly unique contacts. No "email accounts" lever in any plan card. Helper banner: "Plans are based on monthly unique contacts contacted, not total emails sent. Unlimited follow-ups to the same contact. Only new unique recipients count."
- [x] **Mobile responsive** — verified at 390x844 viewport: no horizontal overflow, hero CTAs stack vertically, pricing cards stack to 1 column, demo tabs wrap.
- [x] **Tested**: frontend 100% verified by testing agent (iteration_32), all testids present, Stripe checkout request body intercepted and confirmed correct price_id (e.g. custom_50k → `price_1TV8zTD2HZgi5NSCmPpqjRtm`), no regression on previous backend behaviour.

### ✅ Landing Page Corrections — Real Logo + Real Demo Screenshots (Feb 2026)
- [x] **Original RouteMail logo restored** — Header + Footer now use `<img src="/routemail-logo.png" />` (the pre-existing 65 KB asset). No more AI-generated gradient/Mail-icon mark.
- [x] **Interactive Demo replaced with real platform screenshots** — 6 tabs (Dashboard / Campaign Builder / Drip Campaigns / Email Accounts / Warmup / Analytics) each show a real platform screenshot wrapped in a browser-chrome frame (3 traffic-light dots + `app.routemail.co/...` URL bar) with rounded corners, soft shadow, and a radial-gradient glow. Smooth `framer-motion` transitions between panels.
- [x] **PII-masked screenshots** — captured live via Playwright while logged in as the test user, with TreeWalker substitution masking the real email/name to safe placeholders (`maya@routemail.co`, `sales@routemail.co`, `alex@routemail.co`, `demo@routemail.co`, `Demo User`) before each shot. Verified by tesseract OCR — `drip.tester@example.com` is absent from every screenshot.
- [x] **Removed ~255 lines of dead mock UI** (`DemoDashboard`, `DemoCampaignBuilder`, `DemoDripCampaigns`, `DemoWarmup`, `DemoAnalytics`, `Field`, `Label` helpers).
- [x] Tested: **29/29 desktop + mobile regression PASSED** (iteration_33). All 7 static PNGs return 200 OK; mobile 390x844 has no horizontal overflow.

### 🔄 In Progress
- None currently

### ✅ Registration & Verification - UUID TOKEN SYSTEM (March 2026)
- [x] **Replaced Token Generation with UUID**:
  - Changed from `secrets.token_urlsafe(32)` to `str(uuid.uuid4())`
  - UUID format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (36 chars)
  - No special characters that could cause encoding issues
  - Applied to both registration and resend-verification endpoints
- [x] **Simplified Verification Endpoint**:
  - No URL decoding needed for UUID tokens
  - Direct database lookup: `{"verification_token": token}`
  - Clean token validation (strip whitespace only)
- [x] **Logging Updated**:
  - Registration: `[REGISTRATION] Generated UUID token: <full-uuid>`
  - Verification: `[VERIFICATION] Token value: <full-uuid>`
  - Clear step-by-step logs for debugging
- [x] **Frontend Simplified**:
  - Removed `encodeURIComponent()` - not needed for UUIDs
  - Direct token passing: `/auth/verify-email?token=${token}`
- [x] **Testing Verified**:
  - Registration with UUID: ✅ Pass
  - Multiple consecutive registrations: ✅ Pass
  - Resend verification: ✅ Pass  
  - Frontend E2E registration: ✅ Pass
  - Frontend E2E verification: ✅ Pass
  - Database state: `email_verified: True`, `verification_token: CLEARED`

### 📋 Upcoming Tasks (P1)
1. **Gmail OAuth Integration** - Secure OAuth 2.0 connection for Gmail accounts
   - Files: backend/server.py, frontend/src/pages/EmailAccounts.jsx
2. **Sending Log Export** - CSV download button on Campaign Logs page
   - Files: backend/server.py, frontend/src/pages/CampaignLogs.jsx
3. **Admin Panel Actions** - Implement Suspend/Delete/Role change backend
   - Files: backend/server.py, frontend/src/pages/admin/AdminDashboard.jsx

### 📋 Future Tasks (P2)
1. **Duplicate Campaign** - Add duplicate button for existing campaigns

### ✅ Email Warmup Functionality (May 2026)
- [x] **Backend Warmup System**:
  - Background worker (`run_warmup_worker`) runs every 5 minutes
  - Sends warmup emails between connected accounts
  - ALL warmup subjects include "(RTM)" marker for identification
  - Gradual ramp-up: starting emails → max emails over days
  - Simulates natural email interactions (opens, replies)
  - Random delays between emails (30s-5min)
  - Does NOT interfere with campaign sending
- [x] **Warmup API Endpoints**:
  - `POST /api/accounts/{id}/warmup/enable` - Enable warmup with settings
  - `POST /api/accounts/{id}/warmup/disable` - Disable warmup
  - `POST /api/accounts/{id}/warmup/pause` - Pause warmup
  - `POST /api/accounts/{id}/warmup/resume` - Resume warmup
  - `PUT /api/accounts/{id}/warmup/settings` - Update settings
  - `GET /api/accounts/{id}/warmup/stats` - Get statistics
  - `GET /api/accounts/{id}/warmup/logs` - Get logs
  - `GET /api/warmup/dashboard` - Get dashboard data
- [x] **Warmup Settings Per Account**:
  - Starting emails/day (default: 5, range: 1-20)
  - Max emails/day (default: 50, range: 10-100)
  - Daily increment (default: 5, range: 1-10)
  - Reply rate (default: 40%, range: 30-50%)
- [x] **Frontend UI**:
  - Warmup toggle and controls on Email Accounts page
  - Enable/Disable/Pause/Resume buttons
  - Settings modal for configuration
  - Stats modal showing daily and weekly activity
  - Progress indicator showing warmup day and target
- [x] **Safety Features**:
  - Skips warmup during active campaigns
  - Requires at least 2 connected accounts
  - Human-like delays and content variation
  - Isolated from campaign analytics

### ✅ Pause/Resume Campaign Functionality (March 2026)
- [x] **Backend Endpoints Enhanced**:
  - `POST /api/campaigns/{campaign_id}/pause` - Pauses running or scheduled campaigns
  - `POST /api/campaigns/{campaign_id}/resume` - Resumes paused campaigns
  - Stores `previous_status` and `paused_at` timestamp
  - Logging: `[CAMPAIGN_PAUSED]` and `[CAMPAIGN_RESUMED]` for audit
- [x] **Campaign Status Support**:
  - `draft` - Not started
  - `scheduled` - Waiting for scheduled time
  - `running` - Actively sending emails
  - `paused` - Manually paused by user
  - `paused_daily_limit` - Paused due to daily limit reached
  - `completed` - All emails sent
  - `failed` - Campaign failed
- [x] **Dashboard Campaign List**:
  - Pause button visible for `running` and `scheduled` campaigns
  - Resume button visible for `paused` and `paused_daily_limit` campaigns
  - Status badges with appropriate colors for all statuses
- [x] **Campaign View Page**:
  - Pause Campaign button for running/scheduled campaigns
  - Resume Campaign button for paused campaigns
  - Status badge shows current state
- [x] **Sending Engine Behavior**:
  - `process_campaign_queue` checks `status != "running"` before each email
  - Paused campaigns exit processing loop immediately
  - Scheduled campaign checker only processes `status == "scheduled"`
- [x] **Data Integrity**:
  - Already sent emails preserved
  - Progress counts maintained
  - Logs remain accurate
  - No duplicate sends on resume

---

## File Structure
```
/app/
├── backend/
│   ├── server.py (main API with auth, subscription, campaign endpoints)
│   ├── requirements.txt
│   └── .env (includes STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET)
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── LandingPage.jsx
│   │   │   ├── Campaign.jsx
│   │   │   ├── CampaignLogs.jsx
│   │   │   ├── EmailAccounts.jsx
│   │   │   ├── EmailLists.jsx
│   │   │   ├── ListDetails.jsx
│   │   │   ├── UploadList.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   ├── Subscription.jsx (NEW)
│   │   │   └── admin/
│   │   │       ├── AdminDashboard.jsx
│   │   │       └── AdminUserDetails.jsx
│   │   ├── components/
│   │   │   ├── Sidebar.jsx (includes Subscription nav item)
│   │   │   ├── ProtectedRoute.jsx
│   │   │   ├── RichTextEditor.jsx
│   │   │   └── TawkWidget.jsx
│   │   └── App.js
│   └── package.json
└── memory/
    └── PRD.md
```

## Critical Notes
- Super admin email: dhruvmathur208@gmail.com
- Do NOT use react-quill (crashes) - use custom RichTextEditor.jsx
- Database is MongoDB only
- SMTP passwords are Fernet encrypted
- User passwords are bcrypt hashed
- Email sending is implemented but not connected to live SMTP for testing
- Stripe integration uses LIVE keys - subscriptions are real
- Tawk.to widget only loads on authenticated routes
- Google OAuth uses Emergent Auth (https://auth.emergentagent.com) - NOT a custom backend endpoint
- Plan limits are enforced server-side (accounts, contacts, monthly recipients)
- Logo height: Landing page navbar ~100px, Login/Register 80px, Sidebar 64px
