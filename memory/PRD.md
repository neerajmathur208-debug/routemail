# Multi-Sender Rotational Email Tool - PRD

## Original Problem Statement
Build a simple SaaS web application that allows small businesses to:
- Connect multiple email accounts (SMTP)
- Upload a CSV email list  
- Write one email template with personalization
- Automatically send emails in rotation across connected email accounts
- Limit daily sends per email account (50 emails/day)

## Architecture
- **Frontend**: React 19 with Tailwind CSS, Shadcn UI, react-quill (WYSIWYG editor)
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
- [x] CSV upload with validation & duplicate removal
- [x] Rich text email editor (WYSIWYG)
- [x] Dynamic variable personalization {{column_name}}
- [x] Rotational sending logic (50/day/account limit)
- [x] Auto-pause when all accounts hit daily limit
- [x] Campaign persistence (draft/running/paused/completed)
- [x] Dashboard with stats and all campaigns
- [x] Unsubscribe link auto-appended

## What's Been Implemented (Jan 2026)

### Phase 1 - MVP (Completed)
- [x] Landing page with features, CTA
- [x] Emergent Google OAuth integration
- [x] Protected routes with session management
- [x] Email account management (simulated)
- [x] CSV upload with preview and validation
- [x] Campaign creation and management
- [x] Rotational sending engine (background task)
- [x] Dashboard with stats

### Phase 2 - Full Features (Completed)
- [x] **Rich Text Editor** - WYSIWYG with react-quill (bold, italic, links)
- [x] **SMTP Connection** - Real email sending via SMTP
- [x] **Encrypted Credentials** - Fernet encryption for passwords
- [x] **SMTP Presets** - Gmail, Outlook, Yahoo, Custom
- [x] **Connection Testing** - Test SMTP before saving
- [x] **Campaign Persistence** - Full CRUD with statuses
- [x] **Dynamic Variables** - {{column_name}} from CSV columns
- [x] **Variable Detection** - Extract columns from uploaded CSV
- [x] **Variable Insertion** - Click to insert at cursor
- [x] **Campaign List View** - All campaigns with status/progress
- [x] **Campaign Duplicate** - Copy existing campaigns
- [x] **HTML + Plain Text** - Both versions for emails
- [x] **From Name** - Customizable sender name
- [x] **Account Selection** - Choose which accounts to use

## Database Schema

### Users Collection
- user_id, email, name, picture
- subscription_status (auto-active)
- created_at

### Email Accounts Collection
- account_id, user_id
- account_type (smtp)
- email, display_name
- smtp_host, smtp_port, smtp_username
- smtp_password_encrypted (Fernet)
- smtp_encryption (tls/ssl/none)
- status (connected/error/disconnected)
- daily_limit, daily_send_count, last_send_date

### Email Lists Collection
- list_id, user_id
- name, original_filename
- column_headers (for variables)
- total_rows, valid_emails
- emails (array of row data)

### Campaigns Collection
- campaign_id, user_id
- name, subject, body, body_text, from_name
- list_id, account_ids
- status (draft/running/paused/completed)
- total_emails, sent_count, failed_count
- created_at, updated_at, started_at, completed_at

### Email Queue Collection
- queue_id, campaign_id, user_id
- recipient_email, recipient_data
- assigned_account_id
- status (pending/sent/failed)
- error_message, sent_at

## Prioritized Backlog

### P0 - Critical (Completed)
- [x] Auth flow
- [x] SMTP email sending
- [x] Rich text editor with variables
- [x] Campaign persistence

### P1 - Future Enhancements
- [ ] Gmail OAuth integration (requires Google Cloud credentials)
- [ ] Outlook OAuth integration
- [ ] Scheduled campaigns (send at specific time)
- [ ] Email template library

### P2 - Nice to Have
- [ ] Email open tracking
- [ ] Click tracking
- [ ] A/B testing subject lines

### P3 - Out of Scope (per requirements)
- Multi-step campaigns
- Email warmup
- AI writing tools
- Advanced analytics
- CRM features

## Technical Notes
- SMTP passwords encrypted with Fernet before storage
- Variable replacement using regex: `{{column_name}}`
- Random delay 3-8 seconds between sends (configurable)
- Daily limits reset at midnight UTC
- Failed accounts auto-marked as "error" after 5 failures

## Next Tasks
1. User to obtain Google Cloud credentials for Gmail OAuth
2. Add scheduled campaign feature
3. Consider email template library
