# California Burrito Analytics Dashboard

A web dashboard for ~300,000 restaurant line items (110,478 orders, 6 outlets, Jun 2025 to Jun 2026).

- **Live app:** `<ADD YOUR RENDER URL>`  (free hosting: the first load after idle can take up to a minute)
- **Stack:** MySQL (Aiven) · FastAPI (Python) · React + Vite + Recharts · Docker on Render

## Screenshots
`<ADD 2 SCREENSHOTS HERE: full dashboard and a filtered view, in case the free database is asleep>`

## What it does
- KPI cards: orders, line items (records), revenue, average order value, items sold
- 7 charts: revenue trend (month/day), by outlet, by category, by order type, by payment, orders by hour, top 10 items
- Filters: date range, outlet, category, order type, payment (several values at once)
- Rule-based "quick insights" text, CSV export of the filtered rows (max 100,000), mobile-friendly layout, in-memory cache

## Architecture and data handling
```
data.xlsx --(notebook, once)--> data/orders.csv.gz --(etl/load_mysql.py, once)--> MySQL
                                                                          |
Browser (React) <--JSON-- FastAPI (backend/) <--SQL aggregates---------- MySQL
```
1. **Explore once.** `notebooks/01_explore_and_prepare.ipynb` reads the Excel file, checks quality, and saves a 4 MB compressed CSV. Reading the 13 MB Excel file takes about a minute, so the web app never touches it.
2. **Load once.** `etl/load_mysql.py` creates the table from `etl/schema.sql` (typed columns and indexes) and loads all rows. It adds `revenue = price x quantity`, `order_date`, `order_month`, `order_hour`, then prints totals to compare with the expected numbers.
3. **Serve aggregates, not rows.** Each chart is one SQL `GROUP BY` query. The browser never receives the 300,000 rows.
4. **One service.** FastAPI also serves the built React files, so there is one URL and no cross-site (CORS) setup.

### Why MySQL (and what I weighed)
- The data is read-only and small, so SQLite would also work and is simpler. I chose MySQL because it is a standard server database: the app and the data are separate, many users can read at once, and it matches how a production system is usually built.
- Cost of that choice: an extra service to host, a network hop on every query, and a free database that can be switched off when idle.
- I also considered pre-aggregated summary tables. I did not use them: they cannot be added up for distinct order counts across categories, and indexed queries were fast enough.

## Performance
- Indexes on date, outlet, category, order type, payment and bill number.
- All 9 requests for a screen run in parallel; filter changes wait 300 ms and cancel old requests.
- Gzip responses and a 5-minute in-memory cache keyed by the filters.
- Every API response has an `X-Process-Time-ms` header.

| Query (full data) | Measured on live app |
|---|---|
| KPIs | `<fill in ms>` |
| Monthly trend | `<fill in ms>` |
| Top items | `<fill in ms>` |
| Full dashboard load (browser, warm) | `<fill in s>` |

## Data findings and assumptions
- **A "record" is a line item.** 300,000 line items = 110,478 orders. Orders are always counted with `COUNT(DISTINCT bill_no)`.
- Every order has one outlet, time, order type and payment method (checked), so order-level grouping is safe.
- June 2025 and June 2026 are **partial months** (data starts 17 Jun, ends 16 Jun). The monthly chart shows a note.
- 8,611 rows have price 0: free dips (`Dip - BBQ`, `Dip - Mayo`). They are kept: they count as items sold with ₹0 revenue.
- `Brand` has one value, so there is no brand filter. Outlet is used as the region filter.
- Some delivery orders are paid with "Cash/Card/Coupon". Shown as recorded.
- No currency column: ₹ is assumed.
- Dates are stored as `DATE` and handled as plain strings in the browser to avoid timezone shifts.

## Trade-offs and limits
- Free Aiven database may be powered off if unused; free Render service sleeps when idle (slow first load).
- Cache is per server process and is lost on restart. Fine because the data never changes.
- CSV export is capped at 100,000 rows to protect the small server.
- No login: the data is read-only and there are no user accounts to protect.

## Run locally
1. Python 3.12, Node 20. `python -m venv .venv`, activate it, then `pip install -r backend/requirements.txt pandas openpyxl jupyter`
2. Copy `.env.example` to `.env` and fill `DATABASE_URL` (and `DB_SSL_CA=certs/ca.pem` for Aiven).
3. Load data: `python etl/load_mysql.py`
4. Check the numbers: `python -m tests.verify_reference_numbers`
5. API: `uvicorn backend.main:app --reload --port 8000`
6. Frontend: `cd frontend`, `npm install`, `npm run dev`, open http://localhost:5173

## Deploy (Render, Docker)
New Web Service from this repo, runtime Docker, free plan. Environment variables: `DATABASE_URL`, `DB_SSL_CA=certs/ca.pem`. Health check path: `/api/health`.

## Project structure
```
backend/    FastAPI app, SQL queries (queries.py), database connection
frontend/   React + Vite + Recharts
etl/        schema.sql, load_mysql.py, test_connection.py
notebooks/  01_explore_and_prepare.ipynb
tests/      verify_reference_numbers.py
Dockerfile  builds the React app, then the Python image
```
