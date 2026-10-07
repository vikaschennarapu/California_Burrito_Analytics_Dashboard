// Dates stay as plain "YYYY-MM-DD" strings everywhere (no Date objects -> no timezone bugs).
export function buildQuery(filters, extra = {}) {
  const p = new URLSearchParams();
  if (filters.start) p.set("start", filters.start);
  if (filters.end) p.set("end", filters.end);
  for (const key of ["outlets", "groups", "types", "settlements"]) {
    for (const v of filters[key] || []) p.append(key, v);
  }
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return p.toString();
}

export async function getJson(path, filters = {}, extra = {}, signal) {
  const res = await fetch(`/api/${path}?${buildQuery(filters, extra)}`, { signal });
  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return res.json();
}
