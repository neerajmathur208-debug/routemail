# RouteMail - Email Rotation SaaS Platform

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
8. **Subscription System**: Stripe-integrated yearly subscriptions with plan limits enforcement
9. **Email Verification**: Mandatory email verification before login (2hr token expiry)
10. **Forgot Password**: Secure password reset with rate limiting

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
- `/api/lists` - Create email list (enforces contact limits)
- `/api/campaigns` - CRUD for campaigns
- `/api/campaigns/{id}/start` - Start campaign immediately
- `/api/campaigns/{id}/schedule` - Schedule campaign for later
- `/api/campaigns/{id}/pause` - Pause running campaign
- `/api/campaigns/{id}/resume` - Resume paused campaign
- `/api/campaigns/{id}/logs` - Sending logs

### Admin
- `/api/admin/stats` & `/api/admin/users` - Admin endpoints (super_admin only)

## User Roles
- **user**: Standard access to dashboard, campaigns, email accounts, lists
- **super_admin**: Full access + admin panel (dhruvmathur208@gmail.com)

---

## Implementation Status

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

### ✅ Minor Updates (Feb 2026)
- [x] **Privacy Policy Text Updated**: Company info changed to "Registered in India / RouteMail / Perfect Multimedia / 1036C B3 Tower Spaze iTech Park, Gurgaon, Haryana 122018"
- [x] **Hero Heading Updated**: Removed period from "from Multiple Accounts."
- [x] **Onboarding Popups Fix**: Changed from localStorage to database-backed (`onboarding_completed` field in users collection). Now shows only on first login, persists across sessions and devices.
- [x] **Email Verification Redirect Fix**: 
  - Backend returns `redirect_url` based on `FRONTEND_URL` env var
  - Frontend uses `window.location.href` for absolute redirect to production domain
  - On success → redirects to `{FRONTEND_URL}/dashboard` (https://routemail.co/dashboard in production)
  - Fixed error message parsing to correctly distinguish "invalid" vs "expired" tokens

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
