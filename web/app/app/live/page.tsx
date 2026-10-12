"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, fmt } from "@/lib/api";
import { useResource, useStatus } from "@/components/qp/store";
import { Callout, DataTable, Empty, Field, Headline, PageHeader, Panel, Segmented, Tag, Toggle, Workbench } from "@/components/qp/ui";

const SIGNAL_TONE: Record<string, "pos" | "neg" | "warn" | "brand" | undefined> = {
  "long spread": "brand", "short spread": "brand", "beyond stop": "neg", "inside exit band": "pos", "no signal": undefined,
};

export default function Live() {
  const { status } = useStatus();
  const disc = useResource<any>("/api/discovery");
  const [picked, setPicked] = useState<string[]>([]);
  const [provider, setProvider] = useState("auto");
  const [auto, setAuto] = useState(true);
  const [secs, setSecs] = useState(15);
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);
  const busy = useRef(false);

  const candidates: string[] = useMemo(() => (disc.data?.rows ?? []).map((r: any) => r.pair), [disc.data]);
  useEffect(() => {
    if (!picked.length && disc.data?.rows?.length) {
      const top = disc.data.rows.filter((r: any) => r.eligible).map((r: any) => r.pair);
      setPicked((top.length ? top : disc.data.rows.map((r: any) => r.pair)).slice(0, 4));
    }
  }, [disc.data]);

  const poll = async () => {
    if (busy.current || !picked.length) return;
    busy.current = true;
    try {
      setData(await api(`/api/live?pairs=${encodeURIComponent(picked.join(","))}&provider=${provider}`));
      setErr(null);
      setUpdated(new Date());
    } catch (e: any) {
      setErr(e.message);
    } finally {
      busy.current = false;
    }
  };
  useEffect(() => { poll(); }, [picked.join(","), provider]);
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(poll, Math.max(5, secs) * 1000);
    return () => clearInterval(id);
  }, [auto, secs, picked.join(","), provider]);

  if (!status?.loaded) return (<><PageHeader eyebrow="Research · Live" title="Live monitor" />
    <Empty title="Load daily history first" desc="The live z-score compares today's prices with the model fitted on daily closes, so a dataset must be loaded." action={<Link href="/app/data" className="text-[14px] text-[#0B2545] underline">Go to Data →</Link>} /></>);

  const rows = data?.rows ?? [];
  const active = rows.filter((r: any) => ["long spread", "short spread", "beyond stop"].includes(r.signal)).length;
  const maxZ = rows.reduce((m: number, r: any) => (r.z != null && Math.abs(r.z) > Math.abs(m) ? r.z : m), 0);

  return (
    <>
      <PageHeader eyebrow="Research · Live" title="Live monitor"
        desc="Real-time quotes against the current model. Hedge ratios and the z-score's mean and spread come only from daily closes already loaded, so the live z is an intraday reading against yesterday's distribution — indicative, not a trade instruction."
        right={data && <Tag tone="pos">{data.provider}{updated ? ` · ${updated.toLocaleTimeString()}` : ""}</Tag>} />
      <Workbench rail={
        <Panel title="Watchlist" sub={`${picked.length} of ${candidates.length} tested pairs`}>
          <div className="space-y-4">
            <Field label="Quote provider">
              <Segmented value={provider} onChange={setProvider} options={[{ value: "auto", label: "Auto" }, { value: "alpaca", label: "Alpaca" }, { value: "finnhub", label: "Finnhub" }]} />
            </Field>
            <div className="flex items-center justify-between">
              <Toggle checked={auto} onChange={setAuto} label="Auto-refresh" />
              <select value={secs} onChange={(e) => setSecs(+e.target.value)} className="h-8 rounded-[3px] border border-[#111827]/20 bg-white px-2 text-[13px]">
                {[5, 15, 30, 60].map((s) => <option key={s} value={s}>every {s}s</option>)}
              </select>
            </div>
            <div className="flex max-h-72 flex-wrap gap-1.5 overflow-auto border-t border-[#111827]/10 pt-3">
              {candidates.map((p) => {
                const on = picked.includes(p);
                return (
                  <button key={p} type="button" onClick={() => setPicked(on ? picked.filter((x) => x !== p) : [...picked, p].slice(-12))}
                    className={`num rounded-[3px] border px-2 py-1 text-[12px] transition ${on ? "border-[#0B2545] bg-[#0B2545] text-white" : "border-[#111827]/15 text-[#475569] hover:border-[#111827]/40"}`}>
                    {p}
                  </button>
                );
              })}
            </div>
            {!candidates.length && <p className="text-[13px] text-[#64748B]">Run discovery to choose pairs.</p>}
          </div>
        </Panel>}>
        {err && (
          <Callout tone={err.includes("key") ? "warn" : "neg"} title={err.includes("key") ? "Connect a data provider" : "Live request failed"}>
            {err} {err.includes("key") && <Link href="/app/data" className="text-[#0B2545] underline">Add keys in Data →</Link>}
          </Callout>
        )}
        {data && (
          <>
            <Headline items={[
              { label: "Pairs watched", value: rows.length },
              { label: "Active signals", value: active, tone: active ? "brand" : undefined, note: `|z| ≥ ${data.entry_z}` },
              { label: "Largest |z|", value: fmt.num(maxZ, 2), tone: Math.abs(maxZ) >= data.entry_z ? "warn" : undefined },
              { label: "Last update", value: updated ? updated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—", note: auto ? `refreshing every ${secs}s` : "paused" },
            ]} />
            <Panel title="Live spreads" sub="Spread = y − α − βx at the latest trade prices; z uses the last daily-close window">
              <DataTable rows={rows} rowKey="pair" cols={[
                { key: "pair", label: "Pair", className: "num font-semibold text-[#111827]" },
                { key: "price_y", label: "Last y", align: "right", fmt: (v) => fmt.num(v, 2) },
                { key: "price_x", label: "Last x", align: "right", fmt: (v) => fmt.num(v, 2) },
                { key: "beta", label: "β", align: "right", fmt: (v) => fmt.num(v, 3) },
                { key: "spread", label: "Spread", align: "right", fmt: (v) => fmt.num(v, 3) },
                { key: "z", label: "z", align: "right", fmt: (v) => <span className={v == null ? "" : Math.abs(v) >= (data.entry_z ?? 2) ? "font-semibold text-[#B7791F]" : ""}>{fmt.num(v, 2)}</span> },
                { key: "z", label: "", fmt: (v) => <ZBar z={v} entry={data.entry_z} /> },
                { key: "signal", label: "Signal", fmt: (v, r) => (r.error ? <span className="text-[#DC4545]">{r.error}</span> : <Tag tone={SIGNAL_TONE[v]}>{v}</Tag>) },
                { key: "time_y", label: "Quote time", fmt: (v) => <span className="num text-[#94A3B8]">{v ? String(v).slice(11, 19) : "—"}</span> },
              ]} />
              <p className="mt-3 text-[12.5px] text-[#94A3B8]">
                History ends {rows[0]?.history_end ?? "—"}. Free Alpaca quotes come from the IEX exchange only; Finnhub quotes may lag slightly. Outside market hours these are the last trades.
              </p>
            </Panel>
          </>
        )}
        {!data && !err && <Empty title="Waiting for quotes" desc="Select pairs on the left. Quotes refresh automatically." />}
      </Workbench>
    </>
  );
}

function ZBar({ z, entry = 2 }: { z: number | null; entry?: number }) {
  if (z == null) return null;
  const lim = Math.max(4, entry * 1.6), pct = (v: number) => 50 + (Math.max(-lim, Math.min(lim, v)) / lim) * 50;
  return (
    <div className="relative h-2.5 w-36 bg-[#EEF1F5]">
      <div className="absolute inset-y-0 bg-[#E2E8F0]" style={{ left: `${pct(-entry)}%`, right: `${100 - pct(entry)}%` }} />
      <div className="absolute inset-y-[-3px] w-px bg-[#94A3B8]" style={{ left: "50%" }} />
      <div className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full" style={{ left: `${pct(z)}%`, background: Math.abs(z) >= entry ? "#B7791F" : "#0B2545" }} />
    </div>
  );
}
