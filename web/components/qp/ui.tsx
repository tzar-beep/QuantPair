"use client";
/**
 * QuantPair UI kit — research-note style.
 * Ink on paper: serif headings, hairline rules instead of boxes, tabular numerals,
 * colour only where it carries meaning (gains, losses, warnings, the one navy action).
 */
import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const INK = "text-[#111827]", MUTED = "text-[#64748B]";

export function PageHeader({ eyebrow, title, desc, right }: { eyebrow: string; title: string; desc?: string; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-6 pb-2">
      <div className="max-w-3xl">
        <div className="smallcaps">{eyebrow}</div>
        <h1 className={cn("display mt-3 text-[42px]", INK)}>{title}</h1>
        {desc && <p className="mt-3 text-[15.5px] leading-relaxed text-[#475569]">{desc}</p>}
      </div>
      {right && <div className="flex flex-wrap items-center gap-x-4 gap-y-2">{right}</div>}
    </div>
  );
}

/** A section on a rule. No box, no shadow. */
export function Panel({ title, sub, right, children, className, bodyClass }: {
  title?: string; sub?: string; right?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={cn("border-t border-[#111827]", className)}>
      {(title || right) && (
        <header className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 pt-4">
          <div className="min-w-0">
            <h3 className={cn("serif text-[20px] font-semibold tracking-tight", INK)}>{title}</h3>
            {sub && <p className={cn("mt-0.5 text-[13px]", MUTED)}>{sub}</p>}
          </div>
          {right}
        </header>
      )}
      <div className={cn("pt-4", bodyClass === "p-0" ? "" : bodyClass)}>{children}</div>
    </section>
  );
}

const toneCls = { pos: "text-[#0F9F75]", neg: "text-[#DC4545]", warn: "text-[#B7791F]", brand: "text-[#0B2545]" } as const;
export type Tone = keyof typeof toneCls | undefined;

export function Kpi({ label, value, tone, hint }: { label: string; value: ReactNode; tone?: Tone; hint?: ReactNode }) {
  return (
    <div className="min-w-0 border-b border-[#111827]/10 py-3.5 pr-4">
      <div className={cn("truncate text-[13px]", MUTED)}>{label}</div>
      <div className={cn("num mt-1 truncate text-[22px] font-medium leading-tight", tone ? toneCls[tone] : INK)}>{value}</div>
      {hint && <div className="num mt-0.5 truncate text-[12px] text-[#94A3B8]">{hint}</div>}
    </div>
  );
}

/** Stat sheet: flows into as many columns as fit, every cell on a hairline. */
export function KpiRow({ children }: { children: ReactNode; cols?: number }) {
  return <div className="grid grid-cols-2 gap-x-6 border-t border-[#111827] sm:grid-cols-3 lg:grid-cols-[repeat(auto-fill,minmax(150px,1fr))]">{children}</div>;
}

export function Tag({ tone, children }: { tone?: "pos" | "neg" | "warn" | "brand"; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[12.5px] font-medium", tone ? toneCls[tone] : MUTED)}>
      <span className={cn("size-1.5 rounded-full", tone === "pos" ? "bg-[#0F9F75]" : tone === "neg" ? "bg-[#DC4545]" : tone === "warn" ? "bg-[#B7791F]" : tone === "brand" ? "bg-[#0B2545]" : "bg-[#CBD5E1]")} />
      {children}
    </span>
  );
}

export function Dot({ tone }: { tone: "pos" | "neg" | "warn" | "brand" }) {
  const c = { pos: "bg-[#0F9F75]", neg: "bg-[#DC4545]", warn: "bg-[#B7791F]", brand: "bg-[#0B2545]" };
  return <span className={cn("inline-block size-1.5 rounded-full", c[tone])} />;
}

export function Callout({ tone = "brand", title, children }: { tone?: "pos" | "neg" | "warn" | "brand"; title?: string; children: ReactNode }) {
  const c = { pos: "border-[#0F9F75]", neg: "border-[#DC4545]", warn: "border-[#B7791F]", brand: "border-[#0B2545]" };
  return (
    <div className={cn("border-l-2 py-1 pl-4 text-[14px] leading-relaxed text-[#334155]", c[tone])}>
      {title && <div className={cn("mb-0.5 font-semibold", INK)}>{title}</div>}
      {children}
    </div>
  );
}

export function Warnings({ items }: { items?: string[] }) {
  if (!items?.length) return null;
  return (
    <Callout tone="warn" title="Read before trusting these numbers">
      <ul className="list-disc space-y-0.5 pl-4">{items.map((w) => <li key={w}>{w}</li>)}</ul>
    </Callout>
  );
}

export function Empty({ title, desc, action }: { title: string; desc: string; action?: ReactNode }) {
  return (
    <div className="border-t border-[#111827]/20 py-10">
      <div className={cn("serif text-[22px]", INK)}>{title}</div>
      <p className={cn("mt-2 max-w-xl text-[14.5px] leading-relaxed", MUTED)}>{desc}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error?: string | null }) {
  if (!error) return null;
  return <Callout tone="neg" title="Request failed">{error}</Callout>;
}

export function RunButton({ loading, onClick, children, variant = "default", disabled, full }: {
  loading?: boolean; onClick: () => void; children: ReactNode; variant?: "default" | "outline" | "secondary"; disabled?: boolean; full?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={loading || disabled}
      className={cn("inline-flex h-10 items-center justify-center gap-2 rounded-[3px] px-5 text-[14px] font-medium transition disabled:opacity-60",
        variant === "default" ? "bg-[#0B2545] text-white hover:bg-[#13315C]" : "border border-[#111827]/25 bg-transparent text-[#111827] hover:border-[#111827]",
        full && "w-full")}>
      {loading && <Loader2 className="size-3.5 animate-spin" />}
      {children}
    </button>
  );
}

/** Parameters in a quiet left column, results to the right. */
export function Workbench({ rail, children }: { rail: ReactNode; children: ReactNode }) {
  return (
    <div className="grid items-start gap-10 xl:grid-cols-[300px_minmax(0,1fr)]">
      <div className="rail order-2 xl:order-1 xl:sticky xl:top-28 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto xl:pr-2">{rail}</div>
      <div className="order-1 min-w-0 space-y-10 xl:order-2">{children}</div>
    </div>
  );
}

export function RailGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-3 border-t border-[#111827]/15 pt-4 first:border-0 first:pt-0">
      <div className={cn("text-[13px] font-semibold", INK)}>{title}</div>
      {children}
    </div>
  );
}

export function Field({ label, hint, children, className }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <label className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <span className="text-[12.5px] text-[#475569]">{label}</span>
      {children}
      {hint && <span className="text-[11.5px] text-[#94A3B8]">{hint}</span>}
    </label>
  );
}

const inputCls = "num h-9 w-full rounded-[3px] border border-[#111827]/20 bg-[#FAF9F6] px-2.5 text-[13.5px] text-[#111827] outline-none transition focus:border-[#0B2545] focus:ring-2 focus:ring-[#0B2545]/10";

export function NumInput({ value, onChange, step = 1, min, max }: { value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number }) {
  return <input type="number" value={Number.isFinite(value) ? value : ""} step={step} min={min} max={max}
    onChange={(e) => onChange(parseFloat(e.target.value))} className={inputCls} />;
}

/** Text tabs with an underline — no pills. */
export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[] }) {
  return (
    <div className="flex max-w-full flex-wrap gap-x-4 border-b border-[#111827]/15">
      {options.map((o) => (
        <button key={o.value} type="button" onClick={() => onChange(o.value)}
          className={cn("-mb-px whitespace-nowrap border-b-2 pb-1.5 pt-1 text-[13.5px] transition",
            value === o.value ? "border-[#0B2545] font-semibold text-[#111827]" : "border-transparent text-[#64748B] hover:text-[#111827]")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} className="flex h-9 items-center gap-2.5 text-[13.5px] text-[#334155]">
      <span className={cn("grid size-4 place-items-center rounded-[2px] border transition", checked ? "border-[#0B2545] bg-[#0B2545]" : "border-[#111827]/30 bg-[#FAF9F6]")}>
        {checked && <svg viewBox="0 0 12 12" className="size-3"><path d="M2.5 6.2 5 8.5l4.5-5" fill="none" stroke="#fff" strokeWidth="1.8" /></svg>}
      </span>
      {label}
    </button>
  );
}

export type Col = { key: string; label: string; fmt?: (v: any, row: any) => ReactNode; align?: "left" | "right"; className?: string };

export function DataTable({ rows, cols, maxH = 420, onRow, selected, rowKey = "pair", dense }: {
  rows: any[]; cols: Col[]; maxH?: number; onRow?: (r: any) => void; selected?: string; rowKey?: string; dense?: boolean;
}) {
  const [sort, setSort] = useState<{ k: string; d: 1 | -1 } | null>(null);
  const data = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => {
      const x = a[sort.k], y = b[sort.k];
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      return (x > y ? 1 : -1) * sort.d;
    });
  }, [rows, sort]);
  return (
    <div className="overflow-auto" style={{ maxHeight: maxH }}>
      <table className="w-full border-collapse text-[13px]">
        <thead className="sticky top-0 z-10 bg-[#EEEBE4]">
          <tr>
            {cols.map((c, ci) => (
              <th key={c.key + ci} onClick={() => setSort((s) => ({ k: c.key, d: s?.k === c.key && s.d === -1 ? 1 : -1 }))}
                className={cn("cursor-pointer select-none whitespace-nowrap border-b border-[#111827] px-3 py-2 text-[12.5px] font-semibold text-[#111827] first:pl-0",
                  c.align === "right" ? "text-right" : "text-left")}>
                <span className="inline-flex items-center gap-1">
                  {c.label}
                  {sort?.k === c.key && (sort.d === -1 ? <ArrowDown className="size-3" /> : <ArrowUp className="size-3" />)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((r, i) => (
            <tr key={`${r[rowKey] ?? ""}-${i}`} onClick={onRow ? () => onRow(r) : undefined}
              className={cn("border-b border-[#111827]/10 transition-colors", onRow && "cursor-pointer hover:bg-[#E6E2D9]",
                selected !== undefined && r[rowKey] === selected && "bg-[#DDE3EC]")}>
              {cols.map((c, ci) => (
                <td key={c.key + ci} className={cn("whitespace-nowrap px-3 text-[#1F2937] first:pl-0", dense ? "py-1.5" : "py-2.5", c.align === "right" ? "num text-right" : "text-left", c.className)}>
                  {c.fmt ? c.fmt(r[c.key], r) : r[c.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Bool({ v }: { v: boolean }) {
  return v ? <span className="text-[#0F9F75]">●</span> : <span className="text-[#CBD5E1]">○</span>;
}

/** The few numbers that decide the verdict, set large. */
export function Headline({ items }: { items: { label: string; value: ReactNode; tone?: Tone; note?: ReactNode }[] }) {
  return (
    <div className="grid grid-cols-2 gap-x-8 gap-y-6 border-t border-[#111827] pt-5 md:grid-cols-4">
      {items.map((it) => (
        <div key={it.label} className="min-w-0">
          <div className={cn("text-[13px]", MUTED)}>{it.label}</div>
          <div className={cn("serif mt-1 truncate text-[44px] font-medium leading-none tracking-tight", it.tone ? toneCls[it.tone] : INK)}>{it.value}</div>
          {it.note && <div className="num mt-2 text-[12px] text-[#94A3B8]">{it.note}</div>}
        </div>
      ))}
    </div>
  );
}

/** Folds rarely-changed settings away. */
export function Advanced({ children, label = "Advanced settings" }: { children: ReactNode; label?: string }) {
  return (
    <details className="group col-span-2 border-t border-[#111827]/10 pt-3">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[13px] text-[#475569] hover:text-[#111827] [&::-webkit-details-marker]:hidden">
        <svg viewBox="0 0 12 12" className="size-3 transition-transform group-open:rotate-90"><path d="M4 2.5 7.5 6 4 9.5" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
        {label}
      </summary>
      <div className="mt-3 grid grid-cols-2 gap-3">{children}</div>
    </details>
  );
}

export const selectCls = "h-9 w-full rounded-[3px] border border-[#111827]/20 bg-[#FAF9F6] px-2 text-[13.5px] text-[#111827] outline-none focus:border-[#0B2545]";

/** Shimmering placeholder that mirrors the page layout while data loads. */
export function PageSkeleton() {
  const bar = "rounded-[2px] bg-[#111827]/[0.07] qp-shimmer";
  return (
    <div className="space-y-10" aria-busy="true" aria-label="Loading">
      <div className="space-y-3"><div className={cn(bar, "h-3 w-28")} /><div className={cn(bar, "h-10 w-80")} /><div className={cn(bar, "h-4 w-[32rem] max-w-full")} /></div>
      <div className="grid grid-cols-2 gap-8 border-t border-[#111827]/20 pt-5 md:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <div key={i} className="space-y-2"><div className={cn(bar, "h-3 w-20")} /><div className={cn(bar, "h-10 w-32")} /></div>)}
      </div>
      <div className={cn(bar, "h-64 w-full")} />
    </div>
  );
}
