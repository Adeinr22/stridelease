# Stridelease

Stridelease is a Django-based commercial property operations MVP. It includes a responsive portfolio dashboard, login, property/unit/tenant/lease/payment records, renewal reminder queueing, and a monthly rent collection chart.

## Run locally on Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and create an account from the sign-in page, or sign in with the superuser account. Each account sees only its own portfolio. Use **Switch account** in the sidebar or top bar to sign out and return to sign-in. The application uses SQLite locally; Django’s database setting can be changed when moving to PostgreSQL.

## Deploy to Render

This project is configured for a Render Python web service and a Render PostgreSQL database. The production settings read `DATABASE_URL`, require `DJANGO_SECRET_KEY` when debug mode is off, use WhiteNoise for static files, and enable HTTPS-related cookie/proxy settings.

### 1. Push the project to GitHub

Render deploys from a Git repository. This workspace may not yet be a Git repository. Create a **private** GitHub repository, then run these commands from the project folder in PowerShell, replacing the URL with your repository URL:

```powershell
git init
git add .
git commit -m "Prepare Stridelease for Render"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/stridelease.git
git push -u origin main
```

Check `git status` before adding files. `.gitignore` excludes the local virtual environment and SQLite database. Never commit passwords, database URLs, or production secret keys.

### 2. Create a PostgreSQL database

1. Sign in to [Render](https://dashboard.render.com/).
2. Select **New + → PostgreSQL**.
3. Give the database a name, choose a region, and select a plan. Keep the region the same as the web service you create next.
4. Create the database and wait until Render reports it is available.
5. In its connection details, locate the **Internal Database URL**. Use this URL for `DATABASE_URL` in the web service. Keep it private.

Use PostgreSQL rather than SQLite for the hosted service: Render web-service filesystems are not the right place for persistent application data. Review the current database plan’s expiry, storage, backup, and pricing details before using it for real property or payment records. A demo/free plan is not a substitute for a production backup plan.

### 3. Create the web service

1. Select **New + → Web Service** and connect the GitHub repository.
2. Choose the `main` branch, **Python** as the runtime, and the same region as the database.
3. Set the build and start commands:

   **Build command**

   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate
   ```

   **Start command**

   ```bash
   gunicorn stridelease.wsgi:application --bind 0.0.0.0:$PORT
   ```

4. If Render asks for a health check path, use `/accounts/login/` (it returns the public sign-in page).
5. Add the environment variables in the next section **before the first deployment**, then create the service.

The build command installs dependencies, collects static assets for WhiteNoise, and applies Django migrations before the service starts.

### 4. Set environment variables

Add these in the service’s environment-variable section while creating the service, before its first deployment:

| Key | Value |
| --- | --- |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | Generate a new secret using Render’s **Generate** option. Do not reuse the development key. |
| `DATABASE_URL` | The PostgreSQL database’s **Internal Database URL**. Use Render’s database-link option if it is offered. |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com` |

Save changes and redeploy if Render does not deploy automatically. The `.onrender.com` host entry allows the service’s Render URL. For a custom domain, set `DJANGO_ALLOWED_HOSTS` to a comma-separated list containing the Render host and each custom hostname, for example `stridelease.onrender.com,app.example.com`. Add custom-domain origins to `DJANGO_CSRF_TRUSTED_ORIGINS` as full HTTPS origins, e.g. `https://app.example.com`. Do not include paths or trailing slashes in origin entries.

If you already created the web service, add these values and trigger a redeploy before using the site. Do not leave a public deployment running with `DJANGO_DEBUG` enabled or without its production database and secret key.

### 5. Deploy and verify

1. Open the service’s **Events** or **Logs** page and confirm the build completes, including `collectstatic` and `migrate`.
2. Open the `onrender.com` URL shown in the service overview.
3. Create an account from the sign-in page. New accounts are regular users, not Django administrators.
4. Create a property and tenant, then check the dashboard and notifications. Confirm the page styling loads.
5. Use **Switch account** to sign out, then sign in again.

If you need Django’s `/admin/`, create a superuser from the service’s Shell (when available) by running `python manage.py createsuperuser`. Do not add a superuser password to source control or to a committed seed script.

### 6. Important data and operations notes

- The hosted PostgreSQL database starts separately from local `db.sqlite3`. Deploying does **not** copy local records; use a deliberate, verified data migration if you need to bring local data over.
- Back up production data before schema changes or imports. Keep `python manage.py migrate` in the build command so new migrations are applied during deploy.
- Keep `DJANGO_DEBUG=False` and keep `DJANGO_SECRET_KEY` and `DATABASE_URL` only in Render’s environment settings.
- Django account registration is open to anyone who can reach the deployed site. New signups create isolated, regular user accounts; they do not get access to other accounts’ portfolios.
- Render URLs and plan features can change. Check the current Render documentation and pricing before launching a production property-management service.

### Troubleshooting

- **Invalid HTTP_HOST / Bad Request:** make sure `DJANGO_ALLOWED_HOSTS` contains the exact custom hostname or `.onrender.com`.
- **CSRF verification failed:** add the site’s HTTPS origin (scheme included, no path or trailing slash) to `DJANGO_CSRF_TRUSTED_ORIGINS`, then redeploy.
- **Missing secret key:** set `DJANGO_SECRET_KEY` in the web service environment; production intentionally refuses to start without it.
- **Database connection error:** use the database’s internal URL and place the web service and database in the same Render region.
- **Unstyled page / missing static files:** verify the build ran `collectstatic --no-input` and that the build logs contain no static-file errors.

For current platform details, see Render’s [Django deployment guide](https://render.com/docs/deploy-django), [PostgreSQL connection guide](https://render.com/docs/postgresql-creating-connecting), and [custom domains guide](https://render.com/docs/custom-domains).

## Current MVP

- Public account registration with Django password validation and session-based authentication.
- Account switching via sign-out and sign-in; property and tenant records are scoped to their owner.
- Create, list, edit, and delete properties, units, tenants, and leases. Linked records are protected from accidental deletion.
- Record and browse rent payments.
- View occupancy, monthly collection, upcoming lease expirations, and a six-month collection trend.
- Queue renewal reminders for review; this MVP does not send emails automatically.
- The notification bell shows upcoming lease expirations, overdue payments, and queued renewal reminders.
- Demonstrate a lease-expiry binary search tree, FIFO renewal queue, doubly linked payment history, adjacency graph, and undo stack in `core/dsa.py`.

For an existing database, run `python manage.py migrate` to add account ownership fields. Older records without an owner stay hidden from regular accounts; assign their property and tenant owners in Django admin if needed.

Run the test suite with `python manage.py test`.
