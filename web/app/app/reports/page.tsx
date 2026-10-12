"use client";
import { useEffect, useState } from "react";
import { Download, FileJson, FileText, History } from "lucide-react";
import { API, api, fmt } from "@/lib/api";
import { useJob, useResource, useStatus } from "@/components/qp/store";
import { RailGroup, Workbench, Callout, DataTable, Empty, ErrorNote, PageHeader, Panel, RunButton } from "@/components/qp/ui";

const FILES = [
  { f: "discovery", t: "Discovery table", d: "All tested pairs with p, q, half-life, ranking" },
  { f: "trades", t: "Trade ledger", d: "Entries, exits, costs and P&L per trade" },
  { f: "equity", t: "Equity & exposure", d: "Daily equity, gross / net exposure" },
  { f: "walkforward", t: "Walk-forward windows", d: "Per-window selection and results" },
  { f: "robustness", t: "Robustness grid", d: "Every parameter variant tested" },
];

export default function Reports() {
  const { status, refresh } = useStatus();
  const exps = useResource<any[]>("/api/experiments");
  const job = useJob();
  const [md, setMd] = useState<string>("");
  useEffect(() => { if (status?.loaded) api<string>("/api/report.md").then(setMd).catch(() => {}); }, [status?.loaded]);
  if (!status?.loaded) return (<><PageHeader eyebrow="Output · 06" title="Research reports" /><Empty title="No data loaded" desc="Load prices first." /></>);

  return (
    <>
      <PageHeader eyebrow="Output · 06" title="Research reports"
        desc="Export the experiment exactly as computed: configuration, dataset, methodology, results, limitations. Every saved experiment can be reloaded and reproduced."
 />
      <Workbench rail={
        <Panel title="Exports" sub="computed results only">
          <div className="space-y-4">
            <RailGroup title="Documents">
              <a href={`${API}/api/report.md`} download="quantpair_report.md" className="flex h-9 w-full items-center justify-center gap-2 rounded-[3px] bg-primary text-[13px] font-medium text-primary-foreground hover:brightness-110"><FileText className="size-3.5" />Research report (.md)</a>
              <a href={`${API}/api/export/summary.json`} download="quantpair_summary.json" className="flex h-9 w-full items-center justify-center gap-2 rounded-md border border-line bg-surface-2 text-[13px] hover:bg-accent"><FileJson className="size-3.5" />Config + summary (.json)</a>
            </RailGroup>
            <RailGroup title="Tables (.csv)">
              <div className="space-y-1">
                {FILES.map((x) => (
                  <a key={x.f} href={`${API}/api/export/${x.f}.csv`} className="group flex items-center justify-between rounded-md px-2 py-2 transition hover:bg-accent">
                    <span><span className="block text-[13px] text-foreground">{x.t}</span><span className="block text-[11.5px] text-muted-foreground">{x.d}</span></span>
                    <Download className="size-3.5 shrink-0 text-muted-foreground group-hover:text-brand" />
                  </a>
                ))}
              </div>
              <p className="text-[11.5px] text-muted-foreground">A CSV returns an error until its stage has been run.</p>
            </RailGroup>
          </div>
        </Panel>}>

      <Panel title="Experiment log" sub="config + data range + metrics + package versions"
        right={<RunButton loading={job.loading} onClick={() => job.run(async () => { await api("/api/experiments", {}); await exps.reload(); })}><History className="size-3.5" />Save current experiment</RunButton>}
        bodyClass="p-0">
        <ErrorNote error={job.error} />
        {exps.data?.length ? (
          <DataTable rows={exps.data} rowKey="id" maxH={320} dense cols={[
            { key: "id", label: "Experiment", className: "num text-foreground" }, { key: "timestamp", label: "Saved", className: "num" },
            { key: "results", label: "Segment", fmt: (v) => v?.segment ?? "—" },
            { key: "results", label: "Sharpe", align: "right", fmt: (v) => fmt.num(v?.metrics?.sharpe) },
            { key: "results", label: "Return", align: "right", fmt: (v) => fmt.spct(v?.metrics?.total_return) },
            { key: "id", label: "", align: "right", fmt: (v) => (
              <button className="text-[12px] text-brand hover:underline" onClick={async () => { await api(`/api/experiments/${v}/load`, {}); await refresh(); }}>Load config</button>) },
          ]} />
        ) : <div className="p-5 text-[13px] text-muted-foreground">No saved experiments yet.</div>}
      </Panel>

      <Panel title="Report preview" sub="generated from the current session">
        {md ? <pre className="num max-h-[560px] overflow-auto whitespace-pre-wrap text-[12px] leading-relaxed text-muted-foreground">{md}</pre>
          : <Callout>Run discovery and a backtest to populate the report.</Callout>}
      </Panel>
      </Workbench>
    </>
  );
}
