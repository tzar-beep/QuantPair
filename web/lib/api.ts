export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T = any>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : msg;
    } catch {}
    throw new Error(msg);
  }
  const ct = r.headers.get("content-type") ?? "";
  return (ct.includes("json") ? r.json() : r.text()) as Promise<T>;
}

const nil = (v: any) => v === null || v === undefined || Number.isNaN(v);
export const fmt = {
  pct: (v: any, d = 2) => (nil(v) ? "—" : `${(v * 100).toFixed(d)}%`),
  spct: (v: any, d = 2) => (nil(v) ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(d)}%`),
  num: (v: any, d = 2) => (nil(v) ? "—" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })),
  money: (v: any) => (nil(v) ? "—" : `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`),
  int: (v: any) => (nil(v) ? "—" : Number(v).toLocaleString("en-US")),
  p: (v: any) => (nil(v) ? "—" : v < 0.0001 ? "<0.0001" : Number(v).toFixed(4)),
};
export const tone = (v: any): "pos" | "neg" | undefined => (nil(v) || v === 0 ? undefined : v > 0 ? "pos" : "neg");
