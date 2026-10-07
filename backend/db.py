"""Database connection. Reads DATABASE_URL (and optional DB_SSL_CA) from the environment or .env."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

_url = os.environ["DATABASE_URL"]
_kwargs = {}
if _url.startswith("mysql"):
    # Small pool (free plans allow few connections). pre_ping + recycle stop
    # "connection lost" errors when the server closes idle connections.
    _kwargs = dict(pool_size=3, max_overflow=2, pool_pre_ping=True, pool_recycle=280)
    _ca = os.getenv("DB_SSL_CA")
    if _ca:
        _kwargs["connect_args"] = {"ssl": {"ca": _ca}}

engine = create_engine(_url, **_kwargs)


def run(sql, params=None):
    """Run one query and return a list of dicts."""
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params or {}).mappings()]
