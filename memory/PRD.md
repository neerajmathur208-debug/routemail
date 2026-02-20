# Multi-Sender Rotational Email Tool - PRD

## Original Problem Statement
Build a simple SaaS web application that allows small businesses to:
- Connect multiple email accounts (SMTP)
- Upload multiple CSV email lists  
- Write one email template with personalization
- Automatically send emails in rotation across connected email accounts
- User-configurable daily sending limits per account (10-200)
- View detailed sending logs for completed campaigns

## Architecture
- **Frontend**: React 19 with Tailwind CSS, Shadcn UI, Custom Rich Text Editor
- **Backend**: FastAPI (Python) with async support
- **Database**: MongoDB (Motor async driver)
- **Auth**: Emergent Google OAuth (auto-activated users)
- **Email**: Real SMTP sending with encrypted credentials
- **Encryption**: Fernet (symmetric encryption) for SMTP passwords

## User Personas
1. **Small Business Owner**: Needs to send outreach emails to leads
2. **Sales Rep**: Wants to maximize deliverability by rotating senders
3. **Marketer**: Uploads CSV lists and creates personalized campaigns

## Core Requirements (Static)
- [x] User Authentication via Google OAuth
- [x] Connect multiple SMTP email accounts
- [x] User-configurable daily limits per account (10-200)
- [x] Upload and manage multiple CSV email lists
- [x] Rich text email editor (Custom WYSIWYG)
- [x] Dynamic variable personalization {{column_name}}
- [x] Select email list when creating campaign
- [x] Rotational sending logic with custom daily limits
- [x] Auto-pause when all accounts hit daily limit
- [x] Campaign persistence (draft/running/paused/paused_daily_limit/completed)
- [x] Dashboard with stats and all campaigns
- [x] Detailed sending logs with export to CSV
- [x] Back navigation buttons on all pages
- [x] Unsubscribe link auto-appended

## What's Been Implemented (Dec 2025)

### Phase 1 - MVP (Completed)
- [x] Landing page with features, CTA
- [x] Emergent Google OAuth integration
- [x] Protected routes with session management
- [x] Email account management (SMTP)
- [x] CSV upload with preview and validation
- [x] Campaign creation and management
- [x] Rotational sending engine (background task)
- [x] Dashboard with stats

### Phase 2 - Full Features (Completed)
- [x] **Rich Text Editor** - Custom WYSIWYG (replaced react-quill for React 19 compatibility)
- [x] **SMTP Connection** - Real email sending via SMTP
- [x] **Encrypted Credentials** - Fernet encryption for passwords
- [x] **SMTP Presets** - Gmail, Outlook, Yahoo, Custom
- [x] **Connection Testing** - Test SMTP before saving
- [x] **Campaign Persistence** - Full CRUD with statuses
- [x] **Dynamic Variables** - {{column_name}} from CSV columns
- [x] **Variable Detection** - Extract columns from uploaded CSV
- [x] **Campaign List View** - All campaigns with status/progress
- [x] **Campaign Duplicate** - Copy existing campaigns
- [x] **HTML + Plain Text** - Both versions for emails
- [x] **From Name** - Customizable sender name
- [x] **Account Selection** - Choose which accounts to use

### Phase 3 - User Feature Upgrades (Completed Dec 2025)
- [x] **User-defined Daily Limits** - Per-account limits (10-200) editable on Email Accounts page
- [x] **Multiple Email Lists** - Upload and manage multiple CSV lists
- [x] **List Selection in Campaign** - Dropdown to choose list when creating campaign
- [x] **Campaign Sending Logs** - View detailed logs with sent/failed/pending status
- [x] **Logs Pagination & Filtering** - Search by email, filter by status
- [x] **Export Logs to CSV** - Download sending log data
- [x] **Back Button Navigation** - Consistent back buttons on all pages
- [x] **View Logs Button** - Quick access to logs from Dashboard and Campaign list

### Phase 4 - Full Multi-List Management (Completed Dec 2025)
- [x] **Email Lists Management Page** - New dedicated page at /email-lists
- [x] **List Details Page** - View list with stats, variables, preview at /email-lists/:listId
- [x] **Inline List Renaming** - Edit list names directly in the table
- [x] **List Status Tracking** - Shows "Active" or "Used in Campaign"
- [x] **Column Headers Tooltip** - View available variables on hover
- [x] **Upload Page Integration** - Shows existing lists below upload form
- [x] **Dashboard Quick Start Update** - Shows "X Email Lists Uploaded" instead of contact count
- [x] **Sidebar Navigation Update** - "Email Lists" nav item replaces "Upload List"
- [x] **Delete Protection** - Cannot delete lists used in active campaigns

### Phase 5 - Dashboard Modernization (Completed Dec 2025)
- [x] **Modern Stat Cards** - Elevated cards with soft shadows, rounded corners (2xl), colored icon circles
- [x] **Hover Animations** - Cards lift on hover with smooth transitions
- [x] **Gradient Progress Bars** - Modern gradient progress bars with percentage display
- [x] **Account Usage Redesign** - Cleaner layout with animated progress, percentage shown
- [x] **Quick Start Vertical Cards** - Step-by-step progress-style design with checkmarks
- [x] **Campaign Back Button** - "Back to Dashboard" button on /campaign page
- [x] **Visual Polish** - Consistent border-radius, soft shadows, improved spacing
- [x] **Micro-interactions** - Subtle motion animations throughout

### Phase 6 - Analytics-Style Dashboard (Completed Dec 2025)
- [x] **2-Column Layout** - 70% left / 30% right responsive grid
- [x] **Gradient Hero Card** - Email Accounts card with rose/pink gradient + mini sparkline
- [x] **Area Chart** - "Email Activity Overview" with smooth gradient fill, weekly view
- [x] **Bar Chart Widget** - Weekly stats mini chart in right column
- [x] **Today's Summary Widget** - Sends available, failed emails, lists uploaded
- [x] **Redesigned Account Usage** - Rounded cards, gradient progress bars, percentage
- [x] **Campaign Activity Section** - Modern card rows with progress, status badges
- [x] **Quick Actions Refined** - Compact vertical steps with soft backgrounds
- [x] **Premium Feel** - Warm off-white background (#faf9f7), 20px rounded corners
- [x] **Recharts Integration** - AreaChart, BarChart with custom tooltips

### Phase 7 - Super Admin Panel (Completed Dec 2025)
- [x] **Role-Based Access Control** - Users have `role` field (user/super_admin)
- [x] **Super Admin Assignment** - dhruvmathur208@gmail.com auto-assigned as super_admin
- [x] **Protected Admin Routes** - /admin and /admin/users/:userId with backend enforcement
- [x] **Admin Dashboard** - Platform-wide stats (users, campaigns, emails, accounts, lists)
- [x] **Users Management Table** - Search, filter, pagination, role management
- [x] **User Detail View** - Full user info, accounts, campaigns, lists, sending stats
- [x] **Role Change** - Super admin can change user roles
- [x] **User Deletion** - Delete user and all their data (protected for super_admin)
- [x] **Sidebar Admin Link** - Only visible to super_admin users

## Database Schema

### Users Collection
- user_id, email, name, picture
- subscription_status (auto-active)
- role (user/super_admin) - NEW
- created_at

### Email Accounts Collection
- account_id, user_id
- account_type (smtp)
- email, display_name
- smtp_host, smtp_port, smtp_username
- smtp_password_encrypted (Fernet)
- smtp_encryption (tls/ssl/none)
- status (connected/error/disconnected)
- daily_limit (user-configurable: 10-200), daily_send_count, last_send_date

### Email Lists Collection
- list_id, user_id
- name, original_filename
- column_headers (for variables)
- total_rows, valid_emails
- emails (array of row data)

### Campaigns Collection
- campaign_id, user_id
- name, subject, body, body_text, from_name
- list_id (selected list for this campaign)
- account_ids (selected accounts or all if empty)
- status (draft/running/paused/paused_daily_limit/completed/failed)
- total_emails, sent_count, failed_count
- created_at, updated_at, started_at, completed_at

### Email Queue Collection
- queue_id, campaign_id, user_id
- recipient_email, recipient_data
- assigned_account_id
- status (pending/sent/failed)
- error_message, sent_at

## Prioritized Backlog

### P0 - Critical (All Completed)
- [x] Auth flow
- [x] SMTP email sending
- [x] Rich text editor with variables
- [x] Campaign persistence
- [x] User-defined daily limits
- [x] Multiple lists support
- [x] Campaign logs

### P1 - Future Enhancements
- [ ] Gmail OAuth integration (requires Google Cloud credentials)
- [ ] Outlook OAuth integration
- [ ] Scheduled campaigns (send at specific time)
- [ ] Email template library

### P2 - Nice to Have
- [ ] Email open tracking
- [ ] Click tracking
- [ ] A/B testing subject lines

### P3 - Out of Scope
- Multi-step campaigns
- Email warmup
- AI writing tools
- Advanced analytics
- CRM features

## Technical Notes
- SMTP passwords encrypted with Fernet before storage
- Variable replacement using regex: `{{column_name}}`
- Random delay 3-8 seconds between sends
- Daily limits reset when new day detected
- Failed accounts auto-marked as "error" after 5 failures
- Custom RichTextEditor.jsx replaces react-quill (React 19 incompatible)

## Next Tasks
1. Gmail OAuth integration (user needs Google Cloud credentials)
2. Scheduled campaign feature
3. Email template library
