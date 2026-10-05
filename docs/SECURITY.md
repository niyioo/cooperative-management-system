# Security review

Review of the EMDI Cooperative Management System carried out at the end of the build (Phase 12, October 2026). The design-level security model is in [ARCHITECTURE.md §11](ARCHITECTURE.md#11-security-model). This document records what was checked, what was found and fixed, and what remains for the cooperative to decide or operate.

## Summary

| Area | Status |
|---|---|
| Authentication and sessions | Sound. JWT access token held in memory (15 min); rotating refresh token in an `httpOnly` cookie, blacklisted on use and revoked on password change; API responses are never cached; login, reset and password change are throttled and don't reveal which accounts exist |
| Authorisation | Sound, and **verified automatically**: an access-control sweep exercises every API route (≈530 checks) |
| Data isolation between members | Sound: member endpoints never take a member id; other members' objects return 404 (tested for reads and writes) |
| Financial integrity | Sound: append-only ledger and audit log **enforced by PostgreSQL triggers** (tested), maker–checker with a database check, no delete endpoints |
| Input handling | Improved in this review (JSON-only API, stricter link validation); uploads are type- and size-checked by content signature |
| Dependencies | All known advisories fixed; `pip-audit` and `npm audit` were clean at the time of review |
| Production configuration | Passes `manage.py check --deploy` at warning level |

## How it was reviewed

1. **Automated access-control sweep** (`backend/tests/test_access_control.py`). It walks the whole URL map and checks every route and method against:
   - an anonymous caller: must get 401 everywhere under `/admin/` and `/me/`;
   - a member with no officer role: must get 403 everywhere under `/admin/`;
   - an officer with no roles: must get 403 under `/admin/`, apart from a short, reviewed list of reference endpoints open to any officer, and 403 everywhere under `/me/`.

   A future endpoint that forgets its permission map fails CI.
2. **Member isolation tests**: another member's loans, applications, savings and investment histories, closure requests and notifications return 404 for reads, edits, submits, withdrawals and mark-as-read, and nothing changes.
3. **Database integrity tests** (`backend/tests/test_integrity.py`): raw ORM updates and deletes of posted ledger entries and audit-log rows are refused by the database itself.
4. **Django deploy checks** against `config.settings.prod`.
5. **Dependency audits**: `pip-audit -r requirements/prod.txt` and `npm audit --omit=dev`.
6. **Manual review** of authentication, file handling, report exports, notification links, cookie and CORS settings, throttling and secrets handling.

## Findings fixed in this review

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | Django REST Framework 3.16.1 had two published advisories | Medium | Upgraded to 3.17.2 (`requirements/base.txt`) |
| 2 | Pillow 11.3 had several advisories. Pillow parses uploaded member photos and documents, so these were reachable | High | Upgraded to 12.3 |
| 3 | Frontend dependencies with advisories (axios, form-data, follow-redirects, lodash, dompurify and fflate through unused PDF libraries) | High (transitive) | `npm audit fix`, and removed four unused packages (`jspdf`, `jspdf-autotable`, `date-fns`, `jwt-decode`) |
| 4 | React Router 6: open redirect through backslash paths in `<Link>`/`navigate` | Medium | Upgraded to React Router 7.18. Notification links, the only server-supplied link targets, are now restricted to plain `/member/...` paths on the server and checked again before rendering |
| 5 | The API accepted form-encoded bodies everywhere. Form encodings send an omitted boolean as `False`, so a client could silently clear a flag (e.g. create an inactive department) | Low | The API now accepts **JSON only**; the six file-upload endpoints opt in to multipart. Regression test added |
| 6 | Login and reset throttles counted per gunicorn worker (per-process cache), so the real limit was multiplied by the number of workers | Medium | Production uses a shared cache (database cache by default, Redis optional). The Docker image runs `createcachetable` |
| 7 | The OpenAPI schema (`/api/schema/`) was public in production | Low | Requires a signed-in user in production (the interactive docs were already development-only) |
| 8 | No ESLint configuration, so the lint script could not run | Hygiene | Added `.eslintrc.cjs`; lint is clean with zero warnings and runs in CI |

## Follow-up review (October 2026)

Re-run after the guarantor and monthly-contribution features. `pip-audit`, `npm audit` and `check --deploy` were clean, and the access-control sweep covers the new endpoints. Fixed:

| # | Finding | Severity | Fix |
|---|---|---|---|
| 9 | Only login, password reset and guarantor lookup were rate-limited. A signed-in user, or a script with a stolen token, could hammer heavy endpoints (reports, deduction schedule) | Medium | Every request now counts against a default limit: 600/min per user, 60/min per address when signed out (`API_RATE_USER`, `API_RATE_ANON`). The health check is exempt |
| 10 | Password change was not rate-limited, so someone holding a stolen access token could guess the current password | Medium | 5 attempts per minute per user |
| 11 | API responses had no caching directive, so a browser or proxy could keep the login response (with the access token) or members' financial records | Medium | Every `/api/` response is sent with `Cache-Control: no-store` and `Pragma: no-cache` |
| 12 | The one-time token from activation and reset e-mails stayed in the address bar and browser history after the page opened | Low | The page keeps the token in memory and removes it from the URL straight away |
| 13 | No upper limit on the monthly contribution a member can choose, so a typo could reach the payroll schedule | Low | `max_monthly_contribution` on the savings product, enforced whenever one is set. EMDI chose no maximum for Regular Savings (blank); officers can set one under *Savings › Products* |

Tests: `backend/tests/test_security_hardening.py`.

A second pass looked for loopholes in the business rules as well as the code:

| # | Finding | Severity | Fix |
|---|---|---|---|
| 14 | **Spreadsheet formula injection.** Text starting with `=`, `+`, `-` or `@` (a loan purpose, reason or description) was written into Excel exports as a live formula, which would run when an officer opened the file | High | Every export (reports, statements, deduction schedules, templates, import reports) is saved through one helper that stores such text as plain text |
| 15 | The support console (`/django-admin/`) has its own sign-in page, outside the API login throttle and failed-login audit | Medium | Failed console sign-ins are audited (`auth.admin_login_failed`), and an address is locked out for 15 minutes after 5 failures |
| 16 | **A guarantor could close their account while the loan they guarantee was still running**, be paid out, and leave the loan unsecured | High (financial) | Closure approval and execution are refused while the member guarantees a running loan; the settlement statement lists those guarantees (BR-30) |
| 17 | Loan approval counted "accepted" guarantors without re-checking them, so a guarantor suspended, deactivated or leaving after accepting still counted. A suspended member could also accept | Medium (financial) | Only guarantors who are active and not closing their account can be chosen, accept, or count at approval |
| 18 | **The same month's payroll loan repayments could be posted twice**, by uploading the file again or repeating a row, double-deducting members as long as the total stayed within what was owed | High (financial) | A payroll repayment batch is refused for a loan and month already covered by another payroll batch (posted or awaiting approval), or repeated in the same file, and re-checked at approval. Cash repayments in the same month are still allowed |
| 19 | After a password change, refresh tokens were revoked but an access token already issued kept working for up to 15 minutes | Low | Access tokens issued before the last password change are refused, so a reset after a suspected compromise takes effect at once |

| 20 | **Guarantor exposure was unlimited**: a member with no savings could guarantee any number of loans | Medium (financial) | A member may guarantee loans totalling at most **2× their savings** (cooperative setting `guarantor_savings_multiple`; blank means no limit). Checked when the guarantor is chosen, when the application is submitted and when they accept. Applicants are never told another member's savings (BR-31) |

Tests: `backend/tests/test_security_hardening.py`, `backend/apps/loans/tests/test_loopholes.py`.

## Where things are kept

- **Passwords:** only as one-way Argon2 hashes, in PostgreSQL table `accounts_user` (column `password`). They cannot be read back.
- **Session tokens:** the access token only in the browser tab's memory (lost on reload, renewed from the cookie); the refresh token only in an `httpOnly`, path-scoped cookie (`Secure` in production) that page scripts cannot read, rotated and blacklisted on every use. Neither is written to logs, the audit log or browser storage. JWTs carry only the user id and token metadata, no personal data.
- **Server secrets** (`SECRET_KEY`, database and e-mail passwords): environment variables in `backend/.env` on the server, never in git.
- **Audit log:** database table `audit_auditlog` (append-only, enforced by triggers), shown under *Audit Logs* in the officer portal.
- **Application logs:** standard output (collected by Docker or gunicorn in production), level set by `LOG_LEVEL`.

## Controls verified (no change needed)

- **Passwords:** Argon2, minimum 10 characters plus Django's validators, forced change after a temporary password, single-use reset and activation links that expire.
- **Account enumeration:** login failures and password-reset requests give identical responses for unknown accounts.
- **Brute force:** login is throttled per IP and identifier and per IP; reset requests and password changes are throttled; failed logins are audited; every other request has a default per-user / per-address limit.
- **Token theft:** no token in `localStorage`; the refresh cookie is `httpOnly`, `Secure` and scoped to `/api/v1/auth/`; refresh and logout require `X-Requested-With`, which a cross-site form cannot send.
- **Separation of duties:** an approver can never be the creator (checked in the service and by a database `CHECK`); officers cannot act on their own member records (BR-18, tested per action); you can't grant permissions you don't hold or change your own roles; at least one administrator must remain.
- **Files:** uploads are limited to 5 MB and PDF/JPG/PNG verified by content signature (disguised files are rejected), stored outside the web root, and only served through permission-checked endpoints. Downloads are audited.
- **Exports:** report exports need their own permission and are audited with the filters used. Viewing a member statement is audited too.
- **Output encoding:** React escapes all rendered text; PDF renderers escape markup; spreadsheet cells are written as typed values.
- **Transport and headers (production):** HTTPS redirect, HSTS, secure cookies, `X-Frame-Options: DENY`, `nosniff`, `same-origin` referrer policy; CORS limited to listed origins with no wildcard.
- **Secrets:** none in the repository; production refuses to start without `SECRET_KEY` and explicit `ALLOWED_HOSTS`. The demo command's shared password only works with `DEBUG` on.
- **Errors:** a uniform error envelope; with `DEBUG` off, no stack traces or internals reach clients.

## Recommendations and residual risks

These are deployment or policy decisions for the cooperative rather than code defects:

1. **Host the SPA and API on one site** (e.g. `coop.<domain>` and `api.coop.<domain>`). On different sites the refresh cookie is third-party, and browsers that block those will sign users out on reload. See [DEPLOYMENT.md §1](DEPLOYMENT.md#1-choose-the-hosting-layout).
2. **Set a Content-Security-Policy and HSTS on the SPA host.** GitHub Pages can't set headers; a recommended header set is in DEPLOYMENT.md §4.
3. **Two-factor authentication for officers** is not implemented. Officer accounts can approve money movements, so consider adding TOTP for officer roles in a later release.
4. **Uploaded files are not virus-scanned.** Content-signature checks block disguised executables, but a malicious PDF would be stored as uploaded. Add a scanner (e.g. ClamAV) if documents will be opened on officers' machines at scale.
5. **Backups:** the ledger is the cooperative's financial record. Keep daily, off-site, tested backups of the database and the media directory.
6. **Keep dependencies current:** CI fails on moderate-or-worse npm advisories. Run `pip-audit` monthly (it isn't in CI because it needs network access to the advisory database at run time).
