# RouteMail - Email Rotation SaaS Platform

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
