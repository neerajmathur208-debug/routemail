# RouteMail Test Credentials

## Pre-seeded verified user (for drip campaign + general API testing)
- **Email:** drip.tester@example.com
- **Password:** DripTest123!
- **user_id:** user_35cc629e1385
- **email_verified:** true
- **auth_method:** email

Login via `POST /api/auth/login` with the above credentials. The returned session cookie / `session_token` is used for all authenticated endpoints.

## Notes
- Registration/verification tests create throw-away users with pattern `test.*.{uuid}@example.com` and clean them up afterward.
- Do NOT delete the drip.tester account — it is used by drip-campaign tests and must remain verified.
