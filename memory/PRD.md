# Rotation - Email Rotation SaaS Platform

## Original Problem Statement
Build a simple SaaS web application for small businesses to automatically send emails in rotation across multiple connected email accounts with daily sending limits.

## Core Requirements
1. **Email Account Management**: Connect multiple email accounts (SMTP/IMAP or OAuth)
2. **List Management**: Upload and manage CSV email lists with multiple lists per user
3. **Campaign Management**: Create campaigns with rich text editor, dynamic variables ({column_name}), save/load campaigns with statuses (Draft, Scheduled, Running, Paused, Completed)
4. **Scheduler**: Schedule campaigns to send at a specific date/time or send immediately
5. **Rotational Sending**: Send emails rotationally across accounts with custom daily limits
6. **Sending Logs**: Detailed logs showing sent/failed status and error messages
7. **Admin Panel**: Platform-wide monitoring for super_admin users

## Tech Stack
- **Frontend**: React 19, TailwindCSS, Shadcn UI, Recharts, Framer Motion
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Authentication**: Emergent-managed Google Social Login with RBAC

## Database Schema
- **users**: email, name, google_id, is_active, created_at, role ('user' | 'super_admin')
- **email_accounts**: user_id, email, type, credentials (encrypted), daily_limit, daily_sent_count, status
- **email_lists**: user_id, list_name, original_filename, column_headers, total_rows
- **email_list_contacts**: list_id, contact_data, email, status
- **campaigns**: user_id, name, subject, body, status, email_list_id, total_emails, sent_count, **scheduled_at** (nullable datetime)
- **email_queue**: campaign_id, recipient_email, status, error_message, sent_at

## Campaign Statuses
- `draft` - Campaign saved but not ready to send
- `scheduled` - Campaign scheduled to send at a future time
- `running` - Campaign actively sending emails
- `paused` - Campaign paused by user
- `paused_daily_limit` - Campaign paused due to daily limit reached
- `completed` - Campaign finished sending
- `failed` - Campaign encountered critical error

## Key API Endpoints
- `/api/auth/google/login` & `/api/auth/google/callback` - Authentication
- `/api/auth/me` - Get current user with role
- `/api/email-accounts` - CRUD for email accounts
- `/api/lists` - CRUD for email lists
- `/api/campaigns` - CRUD for campaigns
- `/api/campaigns/{id}/start` - Start campaign immediately
- `/api/campaigns/{id}/schedule` - Schedule campaign for later
- `/api/campaigns/{id}/unschedule` - Unschedule a scheduled campaign
- `/api/campaigns/{id}/pause` - Pause running campaign
- `/api/campaigns/{id}/resume` - Resume paused campaign
- `/api/campaigns/{id}/logs` - Sending logs
- `/api/admin/stats` & `/api/admin/users` - Admin endpoints (super_admin only)

## User Roles
- **user**: Standard access to dashboard, campaigns, email accounts, lists
- **super_admin**: Full access + admin panel (dhruvmathur208@gmail.com)

## Pricing Plans (UI Only - No Stripe Integration)
| Plan | Price | Accounts | Contacts | Features |
|------|-------|----------|----------|----------|
| Free | 14-Day Trial | 3 | 500 | Basic rotation, Scheduler |
| Starter | $99/year | 10 | 7,000 | Full rotation, Scheduler, Unlimited campaigns |
| Growth | $149/year | 15 | 10,000 | Full rotation, Scheduler, Unlimited campaigns |

---

## Implementation Status

### ✅ Completed Features
- [x] User authentication with Google OAuth (Emergent-managed)
- [x] Role-based access control (user/super_admin)
- [x] Multi-list management system with CSV upload
- [x] Campaign creation with rich text editor
- [x] SMTP email account connection
- [x] Analytics-style user dashboard with charts
- [x] Super Admin panel with stats and user management
- [x] Campaign logs page
- [x] Modern public landing page with animations
- [x] Protected routes for admin section

### ✅ Landing Page UX Enhancements (Dec 2025)
- [x] Animated dashboard preview in hero section
- [x] Card-based "Why This Tool Exists" section
- [x] Enhanced "Your Emails Actually Land" visual impact
- [x] Real dashboard preview in "Simple Dashboard" section

### ✅ Scheduler + Landing Page Updates (Dec 2025)
- [x] Campaign Scheduler UI (Send Now / Schedule for Later)
- [x] Date/Time picker for scheduled campaigns
- [x] Backend support for scheduled_at in campaigns
- [x] /schedule and /unschedule API endpoints
- [x] Landing page section reorder (Dashboard Preview after Hero)
- [x] Removed Open Rate from landing page dashboard preview
- [x] Updated pricing to 3 plans (Free, Starter $99/yr, Growth $149/yr)

### 🔄 In Progress
- None currently

### 📋 Upcoming Tasks (P1)
1. **Gmail OAuth Integration** - Secure OAuth 2.0 connection for Gmail accounts
   - Files: backend/server.py, frontend/src/pages/EmailAccounts.jsx
2. **Sending Log Export** - CSV download button on Campaign Logs page
   - Files: backend/server.py, frontend/src/pages/CampaignLogs.jsx
3. **Admin Panel Actions** - Implement Suspend/Delete/Role change backend
   - Files: backend/server.py, frontend/src/pages/admin/AdminDashboard.jsx

### 📋 Future Tasks (P2)
1. **Duplicate Campaign** - Add duplicate button for existing campaigns
   - Files: backend/server.py, frontend/src/pages/Dashboard.jsx
2. **Stripe Integration** - Connect pricing plans to actual payments

---

## File Structure
```
/app/
├── backend/
│   ├── server.py (main API)
│   ├── requirements.txt
│   └── .env
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
│   │   │   ├── AuthCallback.jsx
│   │   │   └── admin/
│   │   │       ├── AdminDashboard.jsx
│   │   │       └── AdminUserDetails.jsx
│   │   ├── components/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── ProtectedRoute.jsx
│   │   │   └── RichTextEditor.jsx
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
- Email sending is implemented but not connected to live SMTP for testing
- Pricing is UI only - no Stripe integration yet
