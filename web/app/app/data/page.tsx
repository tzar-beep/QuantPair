"use client";
import { useEffect, useState } from "react";
import { CloudDownload, Database, Save } from "lucide-react";
import { api, fmt } from "@/lib/api";
import { useJob, useResource, useStatus } from "@/components/qp/store";
import { TimeChart } from "@/components/qp/charts";
import { ProviderPanel, type Source } from "@/components/qp/provider";
import { Empty, Workbench, Callout, DataTable, ErrorNote, Field, Headline, Kpi, KpiRow, PageHeader, Panel, RunButton, Tag } from "@/components/qp/ui";

export default function Data() {
  const { status, setStatus, refresh } = useStatus();
  const quality = useResource<any>(status?.loaded ? "/api/data/quality" : null);
  const job = useJob();
  const [uni, setUni] = useState("");
  const [start, setStart] = useState("2015-01-01");
  const [end, setEnd] = useState("");
  const [px, setPx] = useState<any[]>([]);
  const [pick, setPick] = useState<string[]>([]);
  const [msg, setMsg] = useState("");
  const [src, setSrc] = useState<Source>("live");

  useEffect(() => {
    if (status && !uni) { setUni(status.config.universe.join(", ")); setStart(status.config.start); setEnd(status.config.end ?? ""); }
  }, [status]);
  useEffect(() => { if (status?.data && !pick.length) setPick(status.data.tickers.slice(0, 4)); }, [status?.data]);
  useEffect(() => { if (pick.length && status?.loaded) api(`/api/data/prices?tickers=${pick.join(",")}`).then(setPx).catch(() => {}); }, [pick, status?.data?.retrieved_at]);

  const load = (source: "live" | "snapshot") => job.run(async () => {
    setStatus(await api("/api/data/load", { source: source === "live" ? src : source, universe: uni.split(",").map((x) => x.trim()).filter(Boolean), start, end: end || null }));
    await quality.reload();
    setMsg(source === "live" ? "Live data loaded and validated. Downstream results were cleared." : "Snapshot loaded.");
  });
  const d = status?.data;
  return (
    <>
      <PageHeader eyebrow="Output · 07" title="Data & settings"
        desc="Split- and dividend-adjusted daily closes from Yahoo Finance. Problems are reported, never patched: missing sessions stay missing and are never interpolated."
        right={d && <Tag tone={d.is_snapshot ? "warn" : "pos"}>{d.is_snapshot ? "SNAPSHOT" : "LIVE"} · {d.retrieved_at.slice(0, 16)}</Tag>} />

      <Workbench rail={<div className="space-y-8">
      <ProviderPanel source={src} setSource={setSrc} />
      <Panel title="Universe & range" sub="Peers cointegrate more often than broad ETFs">
        <div className="flex flex-wrap gap-2">
          {Object.entries(status?.presets ?? {}).map(([k, v]: any) => (
            <button key={k} onClick={() => setUni(v.join(", "))}
              className="rounded-md border border-line bg-surface-2 px-3 py-1.5 text-[12.5px] text-muted-foreground transition hover:border-brand/40 hover:text-foreground">{k}</button>
          ))}
        </div>
        <textarea value={uni} onChange={(e) => setUni(e.target.value)} rows={5}
          className="num mt-4 w-full rounded-md border border-input bg-surface-2 p-3 text-[13px] outline-none focus:border-brand/60" />
        <div className="mt-4 grid grid-cols-2 gap-3 [&>button]:col-span-2 [&>button]:w-full">
          <Field label="Start"><input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="num h-9 rounded-md border border-input bg-surface-2 px-3 text-[13px] [color-scheme:dark]" /></Field>
          <Field label="End (blank = today)"><input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="num h-9 rounded-md border border-input bg-surface-2 px-3 text-[13px] [color-scheme:dark]" /></Field>
          <RunButton loading={job.loading} onClick={() => load("live")}><CloudDownload className="size-3.5" />Download from {src === "alpaca" ? "Alpaca" : "Yahoo"}</RunButton>
          {status?.snapshot && <RunButton variant="outline" loading={job.loading} onClick={() => load("snapshot")}><Database className="size-3.5" />Load snapshot</RunButton>}
          {d && !d.is_snapshot && <RunButton variant="outline" onClick={() => job.run(async () => { await api("/api/data/snapshot", {}); await refresh(); setMsg("Snapshot saved to data/ (gitignored)."); })}><Save className="size-3.5" />Save snapshot</RunButton>}
        </div>
        <div className="mt-4 space-y-3">
          <ErrorNote error={job.error} />
          {msg && !job.error && <Callout tone="pos">{msg}</Callout>}
        </div>
      </Panel></div>}>
      {!d && <Empty title="No data loaded" desc="Choose a preset or edit the tickers, then download adjusted daily closes or load a saved snapshot." />}
      {d && (
        <>
          <Headline items={[
            { label: "Symbols", value: d.tickers.length, note: d.failed.length ? `failed: ${d.failed.join(", ")}` : "none failed" },
            { label: "Sessions", value: fmt.int(d.sessions), note: `${d.start} → ${d.end}` },
            { label: "Errors", value: d.errors, tone: d.errors ? "neg" : "pos", note: d.errors ? "see issues below" : "clean" },
            { label: "Warnings", value: d.warnings, tone: d.warnings ? "warn" : undefined },
          ]} />
          <KpiRow cols={6}>
            <Kpi label="All-present dates" value={fmt.int(d.common_dates)} />
          </KpiRow>
          <Panel title="Normalised prices" sub="start = 100 · gaps are missing sessions"
            right={<div className="flex max-w-xl flex-wrap justify-end gap-1">{d.tickers.map((t: string) => (
              <button key={t} onClick={() => setPick(pick.includes(t) ? pick.filter((x) => x !== t) : [...pick, t].slice(-6))}
                className={`num rounded px-1.5 py-0.5 text-[11px] ${pick.includes(t) ? "bg-brand/15 text-brand" : "text-muted-foreground hover:text-foreground"}`}>{t}</button>))}</div>}>
            <TimeChart data={px} height={300} series={pick.map((k) => ({ key: k }))} />
          </Panel>
          {quality.data && (
            <div className="grid gap-6 2xl:grid-cols-[1.5fr_1fr]">
              <Panel title="Per-ticker quality" bodyClass="p-0">
                <DataTable rows={quality.data.summary} rowKey="ticker" maxH={380} dense cols={[
                  { key: "ticker", label: "Ticker", className: "num text-foreground" }, { key: "first", label: "First", className: "num" }, { key: "last", label: "Last", className: "num" },
                  { key: "n_obs", label: "Obs", align: "right" }, { key: "missing_inside", label: "Missing", align: "right" },
                  { key: "max_gap", label: "Max gap", align: "right" }, { key: "max_unchanged_run", label: "Flat run", align: "right" },
                  { key: "status", label: "Status", fmt: (v) => <span className={v === "ok" ? "text-pos" : "text-warn"}>{v}</span> },
                ]} />
              </Panel>
              <Panel title="Issues" bodyClass="p-0">
                {quality.data.issues.length ? (
                  <DataTable rows={quality.data.issues} rowKey="detail" maxH={380} dense cols={[
                    { key: "ticker", label: "Ticker", className: "num" },
                    { key: "severity", label: "Sev.", fmt: (v) => <span className={v === "error" ? "text-neg" : v === "warning" ? "text-warn" : "text-muted-foreground"}>{v}</span> },
                    { key: "detail", label: "Detail", className: "whitespace-normal" },
                  ]} />
                ) : <div className="p-5 text-[13px] text-pos">No data-quality issues detected.</div>}
              </Panel>
            </div>
          )}
        </>
      )}
      </Workbench>
    </>
  );
}
