"""All SQL lives here. Every function takes `run(sql, params) -> list[dict]`
so the same code works with MySQL (production) and any other SQL database (tests).

Rules used everywhere:
- Orders are counted with COUNT(DISTINCT bill_no), never COUNT(*), because one order has many rows.
- Column names come from fixed whitelists in this file; user values are always sent as parameters.
"""

# URL value -> real column name (whitelist, so users can never inject a column name)
DIMS = {
    "outlet": "outlet_name",
    "group": "item_group",
    "order_type": "order_type",
    "settlement": "settlement",
    "item": "item",
}
_FILTERS = [  # (filter field, column, parameter prefix)
    ("outlets", "outlet_name", "o"),
    ("groups", "item_group", "g"),
    ("types", "order_type", "t"),
    ("settlements", "settlement", "s"),
]


def build_where(f):
    clauses, params = [], {}
    if f.get("start"):
        clauses.append("order_date >= :start")
        params["start"] = f["start"]
    if f.get("end"):
        clauses.append("order_date <= :end")
        params["end"] = f["end"]
    for field, col, key in _FILTERS:
        vals = f.get(field) or []
        if vals:
            names = [f":{key}{i}" for i in range(len(vals))]
            clauses.append(f"{col} IN ({', '.join(names)})")
            params.update({f"{key}{i}": v for i, v in enumerate(vals)})
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


def _num(x):
    x = x or 0
    return int(x) if float(x).is_integer() else float(x)


def filter_options(run):
    out = {}
    for name, col in [("outlets", "outlet_name"), ("groups", "item_group"),
                      ("types", "order_type"), ("settlements", "settlement")]:
        out[name] = [r["v"] for r in run(f"SELECT DISTINCT {col} AS v FROM line_items ORDER BY v")]
    r = run("SELECT MIN(order_date) AS lo, MAX(order_date) AS hi FROM line_items")[0]
    out["min_date"], out["max_date"] = str(r["lo"]), str(r["hi"])
    return out


def kpis(run, f):
    where, p = build_where(f)
    r = run(f"""SELECT COUNT(*) AS line_items,
                       COUNT(DISTINCT bill_no) AS orders,
                       COALESCE(SUM(revenue), 0) AS revenue,
                       COALESCE(SUM(quantity), 0) AS items_sold
                FROM line_items {where}""", p)[0]
    out = {k: _num(v) for k, v in r.items()}
    out["avg_order_value"] = round(out["revenue"] / out["orders"], 2) if out["orders"] else 0
    return out


def trend(run, f, grain="month"):
    col = "order_date" if grain == "day" else "order_month"
    where, p = build_where(f)
    rows = run(f"""SELECT {col} AS period, SUM(revenue) AS revenue,
                          COUNT(DISTINCT bill_no) AS orders
                   FROM line_items {where} GROUP BY {col} ORDER BY {col}""", p)
    return [{"period": str(r["period"]), "revenue": _num(r["revenue"]), "orders": _num(r["orders"])}
            for r in rows]


def breakdown(run, f, by, limit=20):
    col = DIMS[by]
    limit = max(1, min(int(limit), 100))
    where, p = build_where(f)
    rows = run(f"""SELECT {col} AS label, SUM(revenue) AS revenue,
                          COUNT(DISTINCT bill_no) AS orders, SUM(quantity) AS items_sold
                   FROM line_items {where} GROUP BY {col}
                   ORDER BY revenue DESC LIMIT {limit}""", p)
    return [{"label": r["label"], "revenue": _num(r["revenue"]),
             "orders": _num(r["orders"]), "items_sold": _num(r["items_sold"])} for r in rows]


def hourly(run, f):
    where, p = build_where(f)
    rows = run(f"""SELECT order_hour AS hour, COUNT(DISTINCT bill_no) AS orders,
                          SUM(revenue) AS revenue
                   FROM line_items {where} GROUP BY order_hour ORDER BY order_hour""", p)
    return [{"hour": int(r["hour"]), "orders": _num(r["orders"]), "revenue": _num(r["revenue"])}
            for r in rows]


def inr(n):
    """Indian digit grouping, e.g. 16694474 -> 1,66,94,474"""
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail, parts = s[:-3], s[-3:], []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def insights(run, f):
    """Simple rule-based text insights computed from the same filtered data."""
    k = kpis(run, f)
    if not k["orders"]:
        return ["No data for the selected filters."]
    out = []
    outlets = breakdown(run, f, "outlet")
    if len(outlets) > 1 and k["revenue"]:
        top = outlets[0]
        out.append(f"{top['label']} is the top outlet with {top['revenue'] / k['revenue']:.0%} "
                   f"of revenue (₹{inr(top['revenue'])}).")
    hrs = hourly(run, f)
    if hrs:
        peak = max(hrs, key=lambda h: h["orders"])
        out.append(f"The busiest hour is {peak['hour']}:00 to {peak['hour'] + 1}:00 "
                   f"with {inr(peak['orders'])} orders.")
    types = breakdown(run, f, "order_type")
    if len(types) > 1 and k["revenue"]:
        t = types[0]
        out.append(f"{t['label']} brings the most revenue ({t['revenue'] / k['revenue']:.0%}).")
    items = breakdown(run, f, "item", 1)
    if items:
        out.append(f"Best-selling item by revenue: {items[0]['label']} (₹{inr(items[0]['revenue'])}).")
    out.append(f"Average order value is ₹{k['avg_order_value']:.0f} across {inr(k['orders'])} orders.")
    return out
