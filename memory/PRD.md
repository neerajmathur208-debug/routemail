# Multi-Sender Rotational Email Tool - PRD

## Original Problem Statement
Build a simple SaaS web application that allows small businesses to:
- Connect multiple email accounts
- Upload a CSV email list  
- Write one email template
- Automatically send emails in rotation across connected email accounts
- Limit daily sends per email account (50 emails/day)

## Architecture
- **Frontend**: React 19 with Tailwind CSS, Shadcn UI components
- **Backend**: FastAPI (Python) with async support
- **Database**: MongoDB (Motor async driver)
- **Auth**: Emergent Google OAuth
- **Payments**: Stripe (test mode, $99/year subscription)
- **Email Sending**: Simulated (no real Gmail OAuth per user request)

## User Personas
1. **Small Business Owner**: Needs to send outreach emails to leads
2. **Sales Rep**: Wants to maximize deliverability by rotating senders
3. **Marketer**: Uploads CSV lists and creates personalized campaigns

## Core Requirements (Static)
- [x] User Authentication via Google OAuth
- [x] Stripe subscription ($99/year) - locks features if inactive
- [x] Connect multiple email accounts (simulated)
- [x] CSV upload with validation & duplicate removal
- [x] Email composer with {first_name} and {company} personalization
- [x] Rotational sending logic (50/day/account limit)
- [x] Auto-pause when all accounts hit daily limit
- [x] Dashboard with stats and progress tracking
- [x] Unsubscribe link auto-appended

## What's Been Implemented (Jan 2026)
- [x] Landing page with features, pricing, CTA
- [x] Emergent Google OAuth integration
- [x] Protected routes with session management
- [x] Stripe checkout integration (test mode)
- [x] Email account management (add/delete)
- [x] CSV upload with preview and validation
- [x] Email list storage with suppression filtering
- [x] Campaign creation and management
- [x] Rotational sending engine (background task)
- [x] Dashboard with account usage stats
- [x] Subscription page with payment flow
- [x] Campaign pause/resume functionality

## Prioritized Backlog
### P0 - Critical (Completed)
- [x] Auth flow
- [x] Payment integration
- [x] Core campaign functionality

### P1 - High Priority  
- [ ] Real Gmail OAuth integration (user skipped)
- [ ] Email warmup (out of scope per requirements)
- [ ] Production Stripe keys

### P2 - Medium Priority
- [ ] Email open tracking
- [ ] Click tracking
- [ ] A/B testing

### P3 - Nice to Have
- [ ] Multi-step campaigns
- [ ] Advanced analytics dashboard

## Next Tasks
1. User to obtain Google Cloud credentials for real Gmail OAuth
2. Switch from test Stripe to production
3. Deploy to production environment

## Technical Notes
- Email sending is **SIMULATED** - rotation logic works, actual SMTP is mocked
- Stripe uses test key `sk_test_emergent`
- Daily limits reset at midnight UTC
- Random 2-5 second delay between sends (configurable to 30-90s for production)
