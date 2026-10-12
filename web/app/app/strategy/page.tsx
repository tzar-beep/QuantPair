"use client";
import { useEffect, useState } from "react";
import { api, fmt, tone } from "@/lib/api";
import { useJob, useResource, useStatus } from "@/components/qp/store";
import { PALETTE, TimeChart } from "@/components/qp/charts";
import { StrategyFields, type Strat } from "@/components/qp/forms";
import { RailGroup, Workbench, Callout, DataTable, Empty, ErrorNote, Field, Headline, Kpi, KpiRow, PageHeader, Panel, RunButton, Segmented, Tag } from "@/components/qp/ui";

export default function StrategyLab() {
  const { status, refresh } = useStatus();
  const disc = useResource<any>("/api/discovery");
  const job = useJob();
  const [s, setS] = useState<Strat | null>(null);
  const [pair, setPair] = useState("");
  const [seg, setSeg] = useState<"validation" | "discovery">("validation");
  const [out, setOut] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { if (status && !s) setS(status.config.strategy); }, [status]);
  useEffect(() => { if (disc.data?.rows?.length && !pair) setPair(disc.data.rows[0].pair); }, [disc.data]);

  const run = () => job.run(async () => {
    const [y, x] = pair.split("/");
    setOut(await api("/api/signals", { y, x, segment: seg, strategy: s }));
    setSaved(false);
  });
  useEffect(() => { if (pair && s && !out) run(); }, [pair, s]);

  if (!disc.data?.ran) return (<><PageHeader eyebrow="Research · 02" title="Strategy lab" /><Empty title="No discovery results" desc="Run pair discovery first; hedge ratios are fitted on its window." /></>);
  const m = out?.metrics;
  const c = out?.counts ?? {};
  return (
    <>
      <PageHeader eyebrow="Research · 02" title="Strategy lab"
        desc="Inspect the spread, causal z-score and every signal event for a single pair. Exploratory by design — final evaluation belongs in Backtest and Walk-forward."
        right={out && <>
          <Tag tone={out.in_sample ? "warn" : "pos"}>{out.in_sample ? "IN-SAMPLE · exploratory" : "OUT-OF-SAMPLE"}</Tag>
          <Tag>fit {out.fit[0]} → {out.fit[1]}</Tag><Tag>eval {out.eval[0]} → {out.eval[1]}</Tag></>} />

      <Workbench rail={s && (
        <Panel title="Parameters">
          <div className="space-y-4">
          <RailGroup title="Pair & period">
            <Field label="Pair">
              <select value={pair} onChange={(e) => { setPair(e.target.value); setOut(null); }}
                className="num h-9 w-full rounded-md border border-input bg-surface-2 px-2 text-[13px] outline-none">
                {disc.data.rows.map((r: any) => <option key={r.pair} value={r.pair}>{r.pair}{r.eligible ? "  ✓ eligible" : r.fdr_pass ? "  · significant" : ""}</option>)}
              </select>
            </Field>
            <Field label="Evaluation period">
              <Segmented value={seg} onChange={(v) => { setSeg(v); setOut(null); }} options={[{ value: "validation", label: "Validation" }, { value: "discovery", label: "In-sample" }]} />
            </Field>
          </RailGroup>
          <RailGroup title="Signal rules"><StrategyFields s={s} set={setS} /></RailGroup>
          <RunButton full loading={job.loading} onClick={run}>Update signals</RunButton>
          <RunButton full variant="outline" onClick={async () => { await api("/api/config", { strategy: s }); await refresh(); setSaved(true); }}>
            {saved ? "Saved to experiment ✓" : "Use in experiment"}
          </RunButton>
          <ErrorNote error={job.error} />
          </div>
        </Panel>
      )}>
      {!out && <Empty title="Computing signals…" desc="Select a pair and parameters." />}

      {out && (
        <>
          <Headline items={[
            { label: "Entries", value: (c.enter_long ?? 0) + (c.enter_short ?? 0), note: `${c.enter_long ?? 0} long · ${c.enter_short ?? 0} short` },
            { label: "Reverted", value: c.exit ?? 0, tone: "pos", note: `${c.stop ?? 0} stopped · ${c.max_hold ?? 0} timed out` },
            { label: "Time in position", value: fmt.pct(out.time_in_position, 0) },
            { label: "Quick backtest", value: fmt.spct(m.total_return), tone: tone(m.total_return), note: `Sharpe ${fmt.num(m.sharpe)} · ${m.n_trades} trades` },
          ]} />
          <KpiRow cols={7}>
            <Kpi label="Long entries" value={c.enter_long ?? 0} />
            <Kpi label="Short entries" value={c.enter_short ?? 0} />
            <Kpi label="Reversion exits" value={c.exit ?? 0} tone="pos" />
            <Kpi label="Stops" value={c.stop ?? 0} tone={c.stop ? "neg" : undefined} />
            <Kpi label="Max-hold exits" value={c.max_hold ?? 0} />
          </KpiRow>
          {out.in_sample && <Callout tone="warn">In-sample view: the pair and its hedge ratio were selected on these same dates. Any profit here is not evidence of an edge.</Callout>}
          <Panel title="Spread" sub="y − α − βx under the selected hedge method">
            <TimeChart data={out.series} series={[{ key: "spread", color: PALETTE.brand, fill: true }]} height={240} />
          </Panel>
          <div className="grid gap-6 2xl:grid-cols-[1.6fr_1fr]">
            <Panel title="Z-score & target position" sub={`entry ±${s?.entry_z} · exit ±${s?.exit_z}${s?.stop_z ? ` · stop ±${s.stop_z}` : ""}`}>
              <TimeChart data={out.series} series={[{ key: "z", color: PALETTE.violet }, { key: "position", color: PALETTE.amber }]} height={260} />
            </Panel>
            <Panel title="Signal events" sub={`${out.events.length} events`} bodyClass="p-0">
              <DataTable rows={out.events} rowKey="date" maxH={300} dense cols={[
                { key: "date", label: "Date", className: "num" },
                { key: "event", label: "Event", fmt: (v) => <span className={v.startsWith("enter") ? "text-brand" : v === "stop" ? "text-neg" : v === "exit" ? "text-pos" : "text-warn"}>{v.replace("_", " ")}</span> },
                { key: "z", label: "z", align: "right", fmt: (v) => fmt.num(v, 2) },
              ]} />
            </Panel>
          </div>
          <Panel title="Hedge-ratio methods" sub="rolling OLS vs Kalman (one-step-ahead) vs the active hedge">
            <TimeChart data={out.betas} series={[{ key: "active", color: PALETTE.brand }, { key: "rolling", color: PALETTE.teal }, { key: "kalman", color: PALETTE.amber }]} height={240} />
            <p className="mt-3 text-[12.5px] text-muted-foreground">Adaptive hedges reduce stale-β risk but can absorb genuine divergence, weakening the reversion signal.</p>
          </Panel>
        </>
      )}
      </Workbench>
    </>
  );
}
