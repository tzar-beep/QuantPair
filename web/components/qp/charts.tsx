"use client";
/**
 * QuantPair charts — hand-built SVG in the research-note style.
 * Real axes, rounded ticks, a zero line, hover crosshair and tooltip.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export const PALETTE = { brand: "#0B2545", amber: "#B7791F", pos: "#0F9F75", neg: "#DC4545", violet: "#6A4C93", teal: "#2F8F80", grey: "#94A3B8" };
export const SERIES = [PALETTE.brand, PALETTE.amber, PALETTE.teal, PALETTE.violet, PALETTE.pos, PALETTE.neg, PALETTE.grey];
export type S = { key: string; color?: string; fill?: boolean; label?: string };

const MONO = "var(--font-geist-mono), ui-monospace, monospace";
const AXIS = "#64748B", GRID = "#E9EEF5", ZERO = "#94A3B8";

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    setW(ref.current.clientWidth);
    const ro = new ResizeObserver((e) => setW(e[0].contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

/** "Nice" tick values (1, 2, 2.5, 5 × 10^k) covering [min, max]. */
function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0];
  if (min === max) { const d = Math.abs(min) || 1; min -= d * 0.5; max += d * 0.5; }
  const raw = (max - min) / Math.max(1, count - 1);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const out: number[] = [];
  for (let v = Math.floor(min / step) * step; v <= max + step * 1e-9; v += step) out.push(+v.toFixed(10));
  if (out[out.length - 1] < max) out.push(out[out.length - 1] + step);
  return out;
}

function fmtVal(v: number | null | undefined, unit?: string, span = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const a = Math.abs(v);
  const s = a >= 10000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : a >= 100 ? v.toFixed(span >= 10 ? 0 : 1) : a >= 10 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : v.toFixed(span < 0.1 ? 3 : 2);
  return unit === "$" ? `${v < 0 ? "−" : ""}$${s.replace("-", "")}` : `${s}${unit ?? ""}`;
}

/** Tick label with just enough decimals for the tick step. */
function fmtTick(v: number, step: number, unit?: string): string {
  const dec = Math.max(0, Math.min(4, Math.ceil(-Math.log10(step) + 1e-9) + (Math.abs(step / 10 ** Math.floor(Math.log10(step)) - 2.5) < 1e-6 ? 1 : 0)));
  const a = Math.abs(v);
  const s = a >= 10000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : (Math.abs(v) < 1e-12 ? 0 : v).toFixed(dec);
  return unit === "$" ? `${v < 0 ? "−" : ""}$${s.replace("-", "")}` : `${s}${unit ?? ""}`;
}

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtDate = (d: string) => `${MON[+d.slice(5, 7) - 1]} ${+d.slice(8, 10)}, ${d.slice(0, 4)}`;

function Legend({ series }: { series: S[] }) {
  if (series.length < 2) return null;
  return (
    <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px] text-[#475569]">
      {series.map((s, i) => (
        <span key={s.key} className="inline-flex items-center gap-2">
          <span className="h-[2px] w-4" style={{ background: s.color ?? SERIES[i] }} />{s.label ?? s.key}
        </span>
      ))}
    </div>
  );
}

export function TimeChart({ data, series, height = 280, unit, legend = true }: {
  data: any[]; series: S[]; height?: number; unit?: string; legend?: boolean;
}) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = data?.length ?? 0;

  const geo = useMemo(() => {
    const vals = data.flatMap((d) => series.map((s) => d[s.key])).filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    if (!vals.length) return null;
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (series.some((s) => s.fill)) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.06;
    // pad only away from zero, so all-negative series (drawdowns) top out at 0
    const ticks = niceTicks(lo < 0 ? lo - pad : lo, hi > 0 ? hi + pad : hi, height >= 260 ? 5 : 4);
    const span = ticks[ticks.length - 1] - ticks[0];
    const labelW = Math.max(...ticks.map((t) => fmtTick(t, ticks[1] - ticks[0], unit).length)) * 6.6 + 14;
    return { ticks, y0: ticks[0], y1: ticks[ticks.length - 1], span, L: labelW };
  }, [data, series, unit, height]);

  if (!n || !geo) return <div ref={ref} className="grid place-items-center text-[13px] text-[#94A3B8]" style={{ height }}>No data for this selection</div>;

  const T = 10, B = 26, R = 12, L = geo.L;
  const iw = Math.max(10, W - L - R), ih = height - T - B;
  const X = (i: number) => L + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
  const Y = (v: number) => T + (1 - (v - geo.y0) / (geo.y1 - geo.y0)) * ih;
  const base = geo.y0 <= 0 && geo.y1 >= 0 ? 0 : geo.y0;

  const pathOf = (key: string) => {
    let d = "", pen = false;
    data.forEach((r, i) => {
      const v = r[key];
      if (typeof v !== "number" || !Number.isFinite(v)) { pen = false; return; }
      d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const areaOf = (key: string) => {
    const idx = data.map((r, i) => (typeof r[key] === "number" ? i : -1)).filter((i) => i >= 0);
    if (!idx.length) return "";
    return `${pathOf(key)} L${X(idx[idx.length - 1]).toFixed(1)},${Y(base).toFixed(1)} L${X(idx[0]).toFixed(1)},${Y(base).toFixed(1)} Z`;
  };

  const first = String(data[0].date ?? ""), last = String(data[n - 1].date ?? "");
  const years = (+last.slice(0, 4) - +first.slice(0, 4)) || 0;
  const xCount = Math.max(2, Math.min(7, Math.floor(iw / 110)));
  const xIdx = Array.from({ length: xCount }, (_, k) => Math.round((k / (xCount - 1)) * (n - 1)));
  const xLabel = (d: string) => (years >= 3 ? d.slice(0, 4) : `${MON[+d.slice(5, 7) - 1]} ${d.slice(2, 4)}`);

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((e.clientX - rect.left - L) / iw) * (n - 1));
    setHover(i >= 0 && i < n ? i : null);
  };
  const hr = hover !== null ? data[hover] : null;

  return (
    <div>
      {legend && <Legend series={series} />}
      <div ref={ref} className="relative" style={{ height }}>
        {W > 0 && (
          <svg width={W} height={height} onMouseMove={onMove} onMouseLeave={() => setHover(null)} className="block">
            {geo.ticks.map((t) => (
              <g key={t}>
                <line x1={L} x2={W - R} y1={Y(t)} y2={Y(t)} stroke={t === 0 ? ZERO : GRID} strokeWidth={1} />
                <text x={L - 8} y={Y(t) + 3.5} textAnchor="end" fontSize="11" fill={AXIS} fontFamily={MONO}>{fmtTick(t, geo.ticks[1] - geo.ticks[0], unit)}</text>
              </g>
            ))}
            {xIdx.map((i, k) => (
              <text key={k} x={X(i)} y={height - 7} textAnchor={k === 0 ? "start" : k === xIdx.length - 1 ? "end" : "middle"}
                fontSize="11" fill={AXIS} fontFamily={MONO}>{xLabel(String(data[i].date))}</text>
            ))}
            {series.map((s, i) => s.fill && <path key={`a${s.key}`} d={areaOf(s.key)} fill={s.color ?? SERIES[i]} fillOpacity={0.08} />)}
            {series.map((s, i) => (
              <path key={s.key} d={pathOf(s.key)} fill="none" stroke={s.color ?? SERIES[i]}
                strokeWidth={i === 0 ? 1.8 : 1.4} strokeLinejoin="round" strokeLinecap="round" />
            ))}
            {hover !== null && (
              <g>
                <line x1={X(hover)} x2={X(hover)} y1={T} y2={T + ih} stroke="#111827" strokeOpacity={0.35} />
                {series.map((s, i) => {
                  const v = data[hover][s.key];
                  return typeof v === "number" && Number.isFinite(v)
                    ? <circle key={s.key} cx={X(hover)} cy={Y(v)} r={3.5} fill="#fff" stroke={s.color ?? SERIES[i]} strokeWidth={2} /> : null;
                })}
              </g>
            )}
          </svg>
        )}
        {hr && hover !== null && (
          <div className="pointer-events-none absolute top-1 z-10 min-w-[150px] rounded-[3px] bg-[#111827] px-3 py-2 text-[12px] text-white shadow-lg"
            style={X(hover) > W * 0.6 ? { right: W - X(hover) + 12 } : { left: X(hover) + 12 }}>
            <div className="num mb-1 text-[11px] text-[#CBD5E1]">{fmtDate(String(hr.date))}</div>
            {series.map((s, i) => (
              <div key={s.key} className="flex items-center justify-between gap-4">
                <span className="inline-flex items-center gap-1.5 text-[#E2E8F0]"><span className="size-2 rounded-full" style={{ background: (s.color ?? SERIES[i]) === PALETTE.brand ? "#8FB3FF" : (s.color ?? SERIES[i]) }} />{s.label ?? s.key}</span>
                <span className="num font-medium">{fmtVal(hr[s.key], unit, geo.span)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** Bar chart with a real y-axis. Negative bars red, positive navy (or `color`). */
export function Bars({ data, x, y, height = 220, color, unit, signed = true }: {
  data: any[]; x: string; y: string; height?: number; color?: string; unit?: string; signed?: boolean;
}) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = data?.length ?? 0;
  if (!n) return <div ref={ref} className="grid place-items-center text-[13px] text-[#94A3B8]" style={{ height }}>No data for this selection</div>;
  const vals = data.map((d) => (typeof d[y] === "number" ? d[y] : 0));
  const ticks = niceTicks(Math.min(0, ...vals), Math.max(0, ...vals), 4);
  const span = ticks[ticks.length - 1] - ticks[0];
  const L = Math.max(...ticks.map((t) => fmtTick(t, ticks[1] - ticks[0], unit).length)) * 6.6 + 14, R = 8, T = 10, B = 26;
  const iw = Math.max(10, W - L - R), ih = height - T - B;
  const bw = iw / n, Y = (v: number) => T + (1 - (v - ticks[0]) / span) * ih;
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(iw / 56))));
  return (
    <div ref={ref} className="relative" style={{ height }}>
      {W > 0 && (
        <svg width={W} height={height} onMouseLeave={() => setHover(null)} className="block">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={L} x2={W - R} y1={Y(t)} y2={Y(t)} stroke={t === 0 ? ZERO : GRID} />
              <text x={L - 8} y={Y(t) + 3.5} textAnchor="end" fontSize="11" fill={AXIS} fontFamily={MONO}>{fmtTick(t, ticks[1] - ticks[0], unit)}</text>
            </g>
          ))}
          {vals.map((v, i) => {
            const y0 = Y(Math.max(0, v)), h = Math.max(1, Math.abs(Y(v) - Y(0)));
            const fill = color ?? (signed && v < 0 ? PALETTE.neg : PALETTE.brand);
            return (
              <g key={i} onMouseEnter={() => setHover(i)}>
                <rect x={L + i * bw} y={T} width={bw} height={ih} fill="transparent" />
                <rect x={L + i * bw + bw * 0.14} y={y0} width={bw * 0.72} height={h} fill={fill} fillOpacity={hover === null || hover === i ? 0.9 : 0.35} />
              </g>
            );
          })}
          {data.map((d, i) => i % every === 0 && (
            <text key={i} x={L + i * bw + bw / 2} y={height - 7} textAnchor="middle" fontSize="11" fill={AXIS} fontFamily={MONO}>{typeof d[x] === "number" ? d[x].toFixed(Math.abs(d[x]) >= 10 ? 0 : 1) : String(d[x])}</text>
          ))}
        </svg>
      )}
      {hover !== null && (
        <div className="pointer-events-none absolute top-1 z-10 rounded-[3px] bg-[#111827] px-3 py-1.5 text-[12px] text-white"
          style={L + hover * bw > W * 0.6 ? { right: W - (L + hover * bw) + 8 } : { left: L + (hover + 1) * bw + 8 }}>
          <span className="num text-[#CBD5E1]">{String(data[hover][x])}</span> · <span className="num font-medium">{fmtVal(vals[hover], unit, span)}</span>
        </div>
      )}
    </div>
  );
}

export function Heatmap({ labels, matrix, rows, cols, fmt = (v: number) => v.toFixed(2), diverging = true }: {
  labels?: string[]; matrix: (number | null)[][]; rows?: string[]; cols?: string[]; fmt?: (v: number) => string; diverging?: boolean;
}) {
  const r = rows ?? labels ?? [], c = cols ?? labels ?? [];
  const flat = matrix.flat().filter((v): v is number => v !== null && Number.isFinite(v));
  const lim = Math.max(1e-9, ...flat.map(Math.abs));
  const bg = (v: number | null) => {
    if (v === null || !Number.isFinite(v)) return "transparent";
    const t = Math.min(1, Math.abs(v) / lim);
    const rgb = diverging && v < 0 ? "220,69,69" : "11,37,69";
    return `rgba(${rgb},${0.06 + 0.8 * t})`;
  };
  const ink = (v: number | null) => (v !== null && Math.abs(v) / lim > 0.55 ? "#fff" : "#111827");
  return (
    <div className="overflow-auto">
      <div className="inline-grid gap-[2px]" style={{ gridTemplateColumns: `78px repeat(${c.length}, minmax(46px, 1fr))` }}>
        <div />
        {c.map((x) => <div key={x} className="num truncate px-1 pb-1.5 text-center text-[11px] text-[#64748B]">{x}</div>)}
        {r.map((y, i) => (
          <div key={y} className="contents">
            <div className="num truncate pr-2 text-right text-[11px] leading-9 text-[#64748B]">{y}</div>
            {c.map((x, j) => {
              const v = matrix[i]?.[j] ?? null;
              return (
                <div key={x} title={`${y} × ${x}`} className="num grid h-9 place-items-center text-[11px]" style={{ background: bg(v), color: ink(v) }}>
                  {v === null ? "" : fmt(v)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChartNote({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-[12.5px] text-[#94A3B8]">{children}</p>;
}
