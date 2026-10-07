"""Checks the live database against totals computed independently with pandas.
Run from the project root:  python -m tests.verify_reference_numbers
"""
from backend import queries as q
from backend.db import run

EMPTY = dict(start=None, end=None, outlets=[], groups=[], types=[], settlements=[])

k = q.kpis(run, EMPTY)
assert k["line_items"] == 300000, k
assert k["orders"] == 110478, k
assert k["revenue"] == 69480952, k
assert k["items_sold"] == 434448, k
assert k["avg_order_value"] == 628.91, k

top = q.breakdown(run, EMPTY, "outlet")[0]
assert top["label"] == "Koramangala" and top["revenue"] == 16694474, top

assert sum(r["revenue"] for r in q.trend(run, EMPTY, "month")) == 69480952
assert sum(r["orders"] for r in q.hourly(run, EMPTY)) == 110478
assert q.kpis(run, dict(EMPTY, outlets=["Nowhere"]))["orders"] == 0

print("All reference checks passed.")
