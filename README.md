# EMDI Cooperative Society — Cooperative Management System

The member and officer portal for the **EMDI Cooperative Society** (Engineering Materials Development Institute, NASENI): membership records, savings (with Christmas Savings kept separate), loans, investments, dividends, account closure, reports and notifications, on one auditable ledger.

- **Members** see their own savings, loans, investments, dividends and transactions, apply for loans, download statements and request account closure. They cannot withdraw savings through the portal.
- **Officers** (Chairman, Secretary, Treasurer, Accountant, Loan and Investment Officers, Auditor, Super Administrator) work within role-based permissions, with maker–checker approval on money movements and a full audit trail.

The design, data model, business rules and API are specified in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**. Deployment is covered in **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**, and the security review in **[docs/SECURITY.md](docs/SECURITY.md)**.

## Features

| Area | What it does |
|---|---|
| Members | Registration (one at a time or spreadsheet import with a dry-run report), profiles, next of kin, documents and photo, status workflow (activate, suspend, reinstate, deactivate), portal invitations |
| Savings | **Monthly statutory contribution** into Regular Savings (member-chosen amount above a minimum, arrears tracking, monthly payroll/IPPIS deduction schedule that uploads straight back as a batch), regular savings products and **Christmas Savings** cycles (January–October, paid out after closing), single contributions, payroll batch uploads, the month-by-month Christmas grid |
| Loans | Products with flat or reducing-balance interest, eligibility checks, member applications with documents and **guarantors chosen by membership number** (asked by e-mail and in the portal; they accept or decline under *Guarantees*), review → approval → disbursement, schedules, repayments (single or payroll batch), overdue tracking, default |
| Investments | Products, member accounts, contributions, liquidations, yearly scheme returns |
| Dividends | December cycles: calculate (closing, average or minimum balance), recalculate, approve, publish to members, pay to savings or externally |
| Ledger | One append-only ledger; balances are always derived from it. Maker–checker approvals, reversals, adjustments, batch uploads with validation reports |
| Account closure | Member request → review → approval (settlement statement frozen) → execution as a settlement batch approved by a second officer. Records are never deleted |
| Reports | 13 reports (membership, savings, contribution arrears, Christmas grid, loans, repayments, overdue, investments, dividends, transactions, financial summary, member statement, closures) on screen, in Excel and PDF; exports are audited |
| Notifications | Automatic member notifications (loan decisions, disbursement, closure steps, dividends, payouts), officer messages to members, announcements for members or officers |
| Administration | Officers and roles (editable permission matrix), cooperative settings, departments, audit log |

## Tech stack

- **Backend:** Python 3.11, Django 5.2, Django REST Framework, Simple JWT, PostgreSQL 16, drf-spectacular (OpenAPI), openpyxl and ReportLab (Excel/PDF), Argon2 password hashing
- **Frontend:** React 18, Vite, React Router 7, TanStack Query, React Hook Form, Tailwind CSS, Recharts, lucide-react
- **Tooling:** pytest (+ pytest-django, factory-boy, pytest-cov), Vitest, ESLint, Docker Compose, GitHub Actions

## Repository layout

```
backend/            Django project
  apps/             one app per module: accounts, members, savings, loans, investments,
                    dividends, ledger, closures, notifications, reports, audit, configuration, common
  config/           settings (base, dev, prod, test), URL routing
  requirements/     base.txt, dev.txt, prod.txt
  tests/            cross-cutting tests (access-control sweep, operations)
frontend/           React single-page app (member portal at /member, officer portal at /admin)
docs/               ARCHITECTURE.md, DEPLOYMENT.md, SECURITY.md
docker-compose.yml  local PostgreSQL + backend + frontend
.env.example        every environment variable, documented
```

## Quick start with Docker

```bash
cp .env.example .env
docker compose up --build
```

Then, in another terminal, load the demo data (development only):

```bash
docker compose exec backend python manage.py seed_demo
```

Open http://localhost:5173/cooperative-management-system/ and sign in with one of the demo accounts listed below. The API runs at http://localhost:8000/api/v1/, with interactive docs at http://localhost:8000/api/docs/ (development only).

## Local setup without Docker

**Requirements:** Python 3.11+, Node.js 20+, PostgreSQL 14+.

1. Create the database (the user needs `CREATEDB` to run the test suite):

   ```bash
   createuser --createdb --pwprompt emdi_coop
   createdb -O emdi_coop emdi_coop
   ```

2. Backend:

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements/dev.txt
   ```

   Create `backend/.env` from the BACKEND section of `.env.example` (`DJANGO_SETTINGS_MODULE=config.settings.dev`, the `DB_*` values, `CORS_ALLOWED_ORIGINS=http://localhost:5173`), then:

   ```bash
   python manage.py migrate
   python manage.py seed_demo      # optional demo data (refuses to run unless DEBUG is on)
   python manage.py runserver
   ```

3. Frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   The app reads `VITE_API_BASE_URL` (default `http://localhost:8000/api/v1`). Open http://localhost:5173/cooperative-management-system/.

### Demo accounts

`seed_demo` creates these accounts and prints their shared password when it finishes:

| Sign in as | Role |
|---|---|
| admin@demo.emdi.test | Super Administrator |
| chairman@demo.emdi.test | Cooperative Chairman |
| secretary@demo.emdi.test | Cooperative Secretary |
| treasurer@demo.emdi.test | Treasurer |
| accountant@demo.emdi.test | Accountant |
| loans@demo.emdi.test | Loan Officer |
| ada@demo.emdi.test or EMDI/COOP/0001 | Member (Ada Okafor) |
| bayo@demo.emdi.test or EMDI/COOP/0002 | Member (Bayo Adeyemi) |

Never run `seed_demo` against a database that holds real data.

### First administrator on a fresh database

```bash
python manage.py createsuperuser
```

Sign in with that account, then add the other officers under **Settings › Officers**. They receive an e-mail link to set their own passwords.

## Running the tests

```bash
cd backend && pytest                      # 886 tests, including the access-control sweep
cd backend && pytest --cov=apps           # with coverage (currently 95%)
cd frontend && npm test                   # Vitest unit tests
cd frontend && npm run lint               # ESLint, zero warnings allowed
```

The backend tests need PostgreSQL (the schema uses PostgreSQL triggers and constraints) and a database user allowed to create the test database. GitHub Actions (`.github/workflows/ci.yml`) runs all of the above plus migration, deploy and API-schema checks and a dependency audit on every push and pull request.

## Key rules the system enforces

- Members can view savings but **cannot withdraw** them through the portal.
- **Every member contributes monthly** into Regular Savings through payroll: an amount they choose, not below the cooperative's minimum. Shortfalls are tracked as arrears.
- **Christmas Savings** runs January–October and is tracked separately from other savings.
- **Loans need officer approval**: review, decision and disbursement are separate steps with separate permissions.
- **Every loan needs a guarantor**: a fellow member, named by membership number, who must accept before the loan can be approved.
- **Dividends** are processed in December from eligible balances.
- **Account closure** needs officer approval, and nothing is ever deleted.
- **Every financial operation is auditable**: posted ledger entries are immutable (corrections are reversals), approvals need a second officer, and every action is in the audit log.
- **Members see only their own data**, and officers act only within their role's permissions.

The full list (BR-01 to BR-29), with where each rule is enforced, is in [docs/ARCHITECTURE.md §10](docs/ARCHITECTURE.md#10-business-rules).
