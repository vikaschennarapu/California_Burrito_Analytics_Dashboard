import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { buildQuery, getJson } from "./api.js";

const COLORS = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];
const inr = (n) => new Intl.NumberFormat("en-IN").format(Math.round(n || 0));
const money = (n) => `₹${inr(n)}`;
const compact = (n) => new Intl.NumberFormat("en-IN", { notation: "compact" }).format(n);
const EMPTY = { start: "", end: "", outlets: [], groups: [], types: [], settlements: [] };

function Card({ title, note, children }) {
  return (
    <section className="card">
      <h3>{title}</h3>
      <div className="chart">{children}</div>
      {note && <p className="note">{note}</p>}
    </section>
  );
}

function BarCard({ title, data, xKey, yKey = "revenue", horizontal = false, note }) {
  return (
    <Card title={title} note={note}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"}
                  margin={{ left: horizontal ? 40 : 0, right: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          {horizontal ? (
            <>
              <XAxis type="number" tickFormatter={compact} />
              <YAxis type="category" dataKey={xKey} width={130} tick={{ fontSize: 12 }} />
            </>
          ) : (
            <>
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={compact} />
            </>
          )}
          <Tooltip formatter={(v) => (yKey === "revenue" ? money(v) : inr(v))} />
          <Bar dataKey={yKey} fill="#2563eb" radius={3} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

function DonutCard({ title, data }) {
  return (
    <Card title={title}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="revenue" nameKey="label" innerRadius="50%" outerRadius="80%">
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={(v) => money(v)} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </Card>
  );
}

function Chips({ label, options, selected, onToggle }) {
  return (
    <div className="chips">
      <span className="chips-label">{label}</span>
      {options.map((o) => (
        <button key={o} type="button"
                className={selected.includes(o) ? "chip on" : "chip"}
                onClick={() => onToggle(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [meta, setMeta] = useState(null);
  const [filters, setFilters] = useState(EMPTY);
  const [grain, setGrain] = useState("month");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 1) load the filter options once, and start with the full date range
  useEffect(() => {
    getJson("filters")
      .then((m) => {
        setMeta(m);
        setFilters({ ...EMPTY, start: m.min_date, end: m.max_date });
      })
      .catch((e) => setError(e.message));
  }, []);

  // 2) reload all charts when filters change (short delay + cancel old requests)
  useEffect(() => {
    if (!meta) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const s = controller.signal;
        const [kpis, trend, outlet, group, type, settlement, hourly, items, insights] =
          await Promise.all([
            getJson("kpis", filters, {}, s),
            getJson("trend", filters, { grain }, s),
            getJson("breakdown", filters, { by: "outlet" }, s),
            getJson("breakdown", filters, { by: "group" }, s),
            getJson("breakdown", filters, { by: "order_type" }, s),
            getJson("breakdown", filters, { by: "settlement" }, s),
            getJson("hourly", filters, {}, s),
            getJson("breakdown", filters, { by: "item", limit: 10 }, s),
            getJson("insights", filters, {}, s),
          ]);
        setData({ kpis, trend, outlet, group, type, settlement, hourly, items, insights });
        setLoading(false);
      } catch (e) {
        if (e.name !== "AbortError") {
          setError(e.message);
          setLoading(false);
        }
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [filters, grain, meta]);

  const toggle = (key, value) =>
    setFilters((f) => ({
      ...f,
      [key]: f[key].includes(value) ? f[key].filter((v) => v !== value) : [...f[key], value],
    }));
  const reset = () => meta && setFilters({ ...EMPTY, start: meta.min_date, end: meta.max_date });

  if (error && !meta) {
    return <div className="page"><p className="error">Could not load the dashboard: {error}</p></div>;
  }
  if (!meta) return <div className="page"><p>Loading…</p></div>;

  const k = data?.kpis;
  return (
    <div className="page">
      <header>
        <h1>California Burrito Analytics Dashboard</h1>
        <p className="sub">
          Sales from {meta.min_date} to {meta.max_date} · amounts in ₹ (assumed) ·
          one order has many line items
        </p>
      </header>

      <section className="filters">
        <div className="dates">
          <label>From
            <input type="date" value={filters.start} min={meta.min_date} max={filters.end || meta.max_date}
                   onChange={(e) => setFilters({ ...filters, start: e.target.value })} />
          </label>
          <label>To
            <input type="date" value={filters.end} min={filters.start || meta.min_date} max={meta.max_date}
                   onChange={(e) => setFilters({ ...filters, end: e.target.value })} />
          </label>
          <button type="button" className="btn" onClick={reset}>Reset</button>
          <a className="btn primary" href={`/api/export.csv?${buildQuery(filters)}`}>
            Export CSV (max 1,00,000 rows)
          </a>
        </div>
        <Chips label="Outlet" options={meta.outlets} selected={filters.outlets} onToggle={(v) => toggle("outlets", v)} />
        <Chips label="Category" options={meta.groups} selected={filters.groups} onToggle={(v) => toggle("groups", v)} />
        <Chips label="Order type" options={meta.types} selected={filters.types} onToggle={(v) => toggle("types", v)} />
        <Chips label="Payment" options={meta.settlements} selected={filters.settlements} onToggle={(v) => toggle("settlements", v)} />
        <p className="note">No chip selected = all values. Choose several chips to compare.</p>
      </section>

      {error && <p className="error">{error}</p>}
      {loading && <p className="loading">Updating…</p>}

      {k && (
        <div className={loading ? "dim" : ""}>
          <div className="kpis">
            <div className="kpi"><span>Orders</span><b>{inr(k.orders)}</b></div>
            <div className="kpi"><span>Line items (records)</span><b>{inr(k.line_items)}</b></div>
            <div className="kpi"><span>Revenue</span><b>{money(k.revenue)}</b></div>
            <div className="kpi"><span>Avg order value</span><b>{money(k.avg_order_value)}</b></div>
            <div className="kpi"><span>Items sold</span><b>{inr(k.items_sold)}</b></div>
          </div>

          <section className="card insights">
            <h3>Quick insights</h3>
            <ul>{data.insights.map((t, i) => <li key={i}>{t}</li>)}</ul>
          </section>

          <div className="grid">
            <Card title="Revenue trend"
                  note={grain === "month"
                    ? "June 2025 and June 2026 are partial months, so their totals look low."
                    : "Daily revenue."}>
              <div className="toggle">
                <button type="button" className={grain === "month" ? "chip on" : "chip"} onClick={() => setGrain("month")}>Month</button>
                <button type="button" className={grain === "day" ? "chip on" : "chip"} onClick={() => setGrain("day")}>Day</button>
              </div>
              <ResponsiveContainer width="100%" height="85%">
                <LineChart data={data.trend} margin={{ right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} minTickGap={30} />
                  <YAxis tickFormatter={compact} />
                  <Tooltip formatter={(v) => money(v)} />
                  <Line type="monotone" dataKey="revenue" stroke="#2563eb" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>

            <BarCard title="Revenue by outlet" data={data.outlet} xKey="label" />
            <DonutCard title="Revenue by category" data={data.group} />
            <BarCard title="Orders by hour of day" data={data.hourly} xKey="hour" yKey="orders" />
            <BarCard title="Top 10 items by revenue" data={data.items} xKey="label" horizontal />
            <DonutCard title="Revenue by order type" data={data.type} />
            <BarCard title="Revenue by payment / channel" data={data.settlement} xKey="label"
                     note="Some delivery orders are paid with Cash/Card/Coupon; shown as recorded." />
          </div>
        </div>
      )}
      <footer>Data: 3,00,000 line items · 1,10,478 orders · built with FastAPI, MySQL and React</footer>
    </div>
  );
}
