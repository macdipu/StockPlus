# ADR 0005 — Public market data; accounts for user-owned data; JWT access + rotating refresh cookie
Status: Accepted (defaults; revisit if the product becomes paid/multi-tenant)
**Decision.** Market data, analysis and scanners are public read. Watchlists and saved scans need an account.
Argon2id password hashes; 15-minute JWT access token; 14-day rotating refresh token in an
`HttpOnly; Secure; SameSite=Lax` cookie; roles `user`, `admin` (admin: trigger sync, ops endpoints).
Secrets only from env/Docker secrets; production refuses the dev default (`Settings.assert_production_safe`).
