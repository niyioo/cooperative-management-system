# Deployment guide

This guide covers a production deployment: the Django API with PostgreSQL, and the React single-page app as static files. Every environment variable is documented in [`.env.example`](../.env.example).

## 1. Choose the hosting layout

The browser keeps the access token in memory and the refresh token in an `httpOnly` cookie set by the API. **Whether that cookie works depends on the SPA and the API being on the same site.**

| Layout | Example | Cookie settings |
|---|---|---|
| **Recommended:** same site, two subdomains | SPA at `https://coop.emdi.example`, API at `https://api.coop.emdi.example` | `REFRESH_COOKIE_SAMESITE=Lax`, `REFRESH_COOKIE_SECURE=True` |
| Same origin (reverse proxy serves both) | `https://coop.emdi.example/` and `https://coop.emdi.example/api/` | as above |
| Different sites | SPA on `niyioo.github.io`, API on `*.onrender.com` | `REFRESH_COOKIE_SAMESITE=None`, `REFRESH_COOKIE_SECURE=True` |

The last layout works today, but browsers increasingly block third-party cookies (Safari already does). Users would then be signed out whenever they reload the page. Use custom domains on one site for production.

## 2. Database

PostgreSQL 14 or newer (16 recommended). The schema relies on PostgreSQL triggers (the ledger and audit log are append-only) and partial unique indexes, so other databases are not supported.

- Create a dedicated database and user. The application user needs no superuser rights.
- Set `DATABASE_URL=postgres://user:password@host:5432/dbname`, or the `DB_*` variables.
- **Back up daily** (`pg_dump --format=custom`) and test restores. The ledger is the cooperative's financial record.

## 3. Backend

### Required environment

```
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<50+ random characters>
ALLOWED_HOSTS=api.coop.emdi.example
DATABASE_URL=postgres://...
CORS_ALLOWED_ORIGINS=https://coop.emdi.example
CSRF_TRUSTED_ORIGINS=https://coop.emdi.example
FRONTEND_URL=https://coop.emdi.example/#        # hash router: keep the "#"
NUM_PROXIES=1                                    # proxies in front of Django (1 on Render/most PaaS)
EMAIL_HOST=... EMAIL_HOST_USER=... EMAIL_HOST_PASSWORD=... DEFAULT_FROM_EMAIL=...
MEDIA_ROOT=/var/lib/emdi-coop/media              # persistent disk, outside the web root
```

Generate a secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

`config.settings.prod` refuses to start without `SECRET_KEY` and explicit `ALLOWED_HOSTS` (no wildcards). It turns on HTTPS redirect, HSTS (one year), secure cookies, `X-Frame-Options: DENY`, `nosniff` and a strict referrer policy.

### With Docker (any container host, or Render "Docker" service)

```bash
docker build -t emdi-coop-api ./backend
docker run --env-file backend/.env.production -p 8000:8000 -v /var/lib/emdi-coop/media:/var/lib/emdi-coop/media emdi-coop-api
```

On start, the image runs `collectstatic`, `migrate` and `createcachetable`, then gunicorn (`WEB_CONCURRENCY` workers, default 3, on `$PORT`).

### Without Docker

```bash
pip install -r requirements/prod.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py createcachetable
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

### Render (native Python service)

- **Root directory:** `backend`
- **Build command:** `pip install -r requirements/prod.txt && python manage.py collectstatic --noinput`
- **Start command:** `python manage.py migrate --noinput && python manage.py createcachetable && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
- Add a **persistent disk** mounted at the `MEDIA_ROOT` path. Member photos, documents and closure attachments live there, and Render's normal filesystem is wiped on every deploy.
- Health check path: `/api/v1/health/`

### Rate limiting cache

Login and password-reset throttles keep their counters in the cache. Production uses the **database cache** by default, which `createcachetable` creates, so all gunicorn workers share the counters. For Redis instead, set `CACHE_URL=redis://host:6379/0` and add `redis` to the requirements.

### First administrator

```bash
python manage.py createsuperuser
```

Then sign in and create the officers under **Settings › Officers**. Each officer gets an e-mail link to set their password. Do **not** run `seed_demo` in production.

### Go-live data

Follow [ARCHITECTURE.md §12](ARCHITECTURE.md#12-go-live-data-migration):
1. Import departments and members (**Members › Import**: dry run, then commit).
2. Post opening balances as batches (**Transactions › Batches**: savings and investment opening balances), approved by a second officer.
3. Reconcile the imported totals (the savings, investments and financial-summary reports) against the source records before inviting members.

## 4. Frontend

Build with the API's public URL:

```bash
cd frontend
npm ci
VITE_API_BASE_URL=https://api.coop.emdi.example/api/v1 npm run build
```

The output in `frontend/dist/` is static. The app is built for the path `/cooperative-management-system/` (`base` in `vite.config.js`). Change `base` if you serve it from the domain root.

- **Hash URLs (default):** links look like `/#/member/loans`, and any static host works with no configuration. This is required on GitHub Pages: `npm run deploy` publishes `dist/` with `gh-pages`.
- **Clean URLs:** build with `VITE_ROUTER=browser`, and have the host rewrite unknown paths to `index.html`.

### Recommended response headers for the SPA host

GitHub Pages cannot set headers. On Netlify, Cloudflare Pages, nginx or similar, add:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' https://api.coop.emdi.example; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

(`style-src 'unsafe-inline'` is needed for the charts' inline styles. No inline scripts are used.)

## 5. After deploying

- Visit `https://api.../api/v1/health/`. It should return `{"status": "ok"}`.
- Sign in as the first administrator and check **Settings › Cooperative** (name, membership-number format, maker–checker types, overdue grace days).
- Send yourself a password reset to confirm e-mail delivery and the link format (`FRONTEND_URL`).
- The interactive API docs (`/api/docs/`) exist only with `DEBUG` on. In production the raw schema at `/api/schema/` needs a signed-in user.

## 6. Upgrading

```bash
git pull
pip install -r requirements/prod.txt     # or rebuild the image
python manage.py migrate --noinput        # the Docker image does this on start
cd frontend && npm ci && npm run build
```

Migrations are committed to the repository and run forward only. Take a database backup before every upgrade.

## 7. Operations checklist

- [ ] Daily database backups, kept off the server, with a tested restore
- [ ] Media directory backed up with the database (documents are referenced by path)
- [ ] HTTPS on both hosts; HSTS preload only if every subdomain is HTTPS-only (`SECURE_HSTS_PRELOAD=True`)
- [ ] `DEBUG` off (production settings force it), and no `.env` file in the image or repository
- [ ] SMTP credentials stored in the platform's secret store
- [ ] Log retention for the application logs (stdout); the audit log lives in the database
- [ ] Dependency updates reviewed monthly (`pip-audit -r requirements/prod.txt`, `npm audit --omit=dev`); CI runs the npm audit on every push
