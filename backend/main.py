"""FastAPI app: JSON API for the dashboard + serves the built React app."""
import csv
import io
import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import queries as q
from .db import engine, run

EXPORT_LIMIT = 100_000   # protects the small free server
CACHE_SECONDS = 300

app = FastAPI(title="California Burrito Analytics API")
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_timing(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - start) * 1000:.0f}"
    return response


# ---- tiny in-memory cache (same filters -> same answer, data never changes) ----
_cache, _lock = {}, Lock()


def cached(key, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    value = fn()
    with _lock:
        if len(_cache) > 500:
            _cache.clear()
        _cache[key] = (now, value)
    return value


def _date(v: Optional[str]):
    if not v:
        return None
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Dates must look like 2025-08-31")
    return v


def get_filters(
    start: Optional[str] = None,
    end: Optional[str] = None,
    outlets: list[str] = Query(default=[]),
    groups: list[str] = Query(default=[]),
    types: list[str] = Query(default=[]),
    settlements: list[str] = Query(default=[]),
):
    start, end = _date(start), _date(end)
    if start and end and start > end:
        raise HTTPException(400, "start must not be after end")
    return {"start": start, "end": end, "outlets": outlets, "groups": groups,
            "types": types, "settlements": settlements}


def _key(name, f, *extra):
    return (name, f["start"], f["end"], tuple(sorted(f["outlets"])), tuple(sorted(f["groups"])),
            tuple(sorted(f["types"])), tuple(sorted(f["settlements"])), *extra)


@app.get("/api/health")
def health():
    run("SELECT 1 AS ok")      # also proves the database is reachable
    return {"status": "ok"}


@app.get("/api/filters")
def filters():
    return cached(("filters",), lambda: q.filter_options(run))


@app.get("/api/kpis")
def kpis(f=Depends(get_filters)):
    return cached(_key("kpis", f), lambda: q.kpis(run, f))


@app.get("/api/trend")
def trend(grain: Literal["day", "month"] = "month", f=Depends(get_filters)):
    return cached(_key("trend", f, grain), lambda: q.trend(run, f, grain))


@app.get("/api/breakdown")
def breakdown(by: Literal["outlet", "group", "order_type", "settlement", "item"],
              limit: int = 20, f=Depends(get_filters)):
    return cached(_key("breakdown", f, by, limit), lambda: q.breakdown(run, f, by, limit))


@app.get("/api/hourly")
def hourly(f=Depends(get_filters)):
    return cached(_key("hourly", f), lambda: q.hourly(run, f))


@app.get("/api/insights")
def insights(f=Depends(get_filters)):
    return cached(_key("insights", f), lambda: q.insights(run, f))


@app.get("/api/export.csv")
def export_csv(f=Depends(get_filters)):
    where, params = q.build_where(f)
    sql = (f"SELECT bill_no, outlet_name, order_datetime, item_group, order_type, item, "
           f"price, quantity, revenue, settlement FROM line_items {where} "
           f"ORDER BY id LIMIT {EXPORT_LIMIT}")

    def generate():
        with engine.connect().execution_options(stream_results=True) as conn:
            result = conn.execute(text(sql), params)
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(result.keys())
            n = 0
            for row in result:
                writer.writerow(row)
                n += 1
                if n % 2000 == 0:
                    yield buf.getvalue()
                    buf.seek(0)
                    buf.truncate(0)
            yield buf.getvalue()

    return StreamingResponse(generate(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=orders_export.csv"})


# ---- serve the built React app (exists only after `npm run build` / Docker build) ----
DIST = Path(__file__).resolve().parent.parent / "frontend_dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        target = (DIST / full_path).resolve()
        if full_path and target.is_file() and DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(DIST / "index.html")