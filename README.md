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

Open `http://127.0.0.1:8000/` and create an account from the sign-in page, or sign in with the superuser account. Each account sees only its own portfolio. Use **Switch account** in the sidebar to sign out and return to sign-in. The application uses SQLite locally; Django’s database setting can be changed when moving to PostgreSQL.

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
