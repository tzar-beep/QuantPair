"use client";
import { useEffect, useMemo, useState } from "react";
import { api, fmt, tone } from "@/lib/api";
import { useJob, useResource, useStatus } from "@/components/qp/store";
import { Bars, Heatmap, PALETTE, TimeChart } from "@/components/qp/charts";
import {
  Workbench,
  Callout, DataTable, Empty, ErrorNote, Field, Headline, Kpi, KpiRow, NumInput, PageHeader, Panel, RunButton, Segmented, Tag, Toggle, Warnings,
} from "@/components/qp/ui";

type Tab = "wf" | "split" | "grid" | "ml";
const TABS = [{ value: "wf", label: "Walk-forward" }, { value: "split", label: "IS / Val / Test" }, { value: "grid", label: "Robustness" }, { value: "ml", label: "ML filter" }];
const SEL = [{ value: "fdr", label: "FDR-significant" }, { value: "raw", label: "Raw p (exploratory)" }];

export default function Validation() {
  const { status } = useStatus();
  const [tab, setTab] = useState<Tab>("wf");
  if (!status?.loaded) return (<><PageHeader eyebrow="Validation · 05" title="Walk-forward validation" /><Empty title="No data loaded" desc="Load prices first." /></>);
  return (
    <>
      <PageHeader eyebrow="Validation · 05" title="Out-of-sample validation"
        desc="A beautiful in-sample equity curve proves nothing. Re-discover pairs from trailing data only, trade the next window, and count every variant you try."
        right={<Segmented value={tab} onChange={setTab} options={TABS as any} />} />
      {tab === "wf" && <WalkForward />}
      {tab === "split" && <Splits />}
      {tab === "grid" && <Grid />}
      {tab === "ml" && <ML />}
    </>
  );
}

function WalkForward() {
  const { status, refresh } = useStatus();
  const res = useResource<any>("/api/walkforward");
  const job = useJob();
  const [w, setW] = useState<any>(null);
  useEffect(() => { if (status && !w) setW(status.config.walkforward); }, [status]);
  const r = res.data?.ran ? res.data : null;
  const warns = useMemo(() => {
    if (!r) return [];
    const out: string[] = [];
    if (r.summary.traded < 3) out.push(`Only ${r.summary.traded} windows traded at all — out-of-sample evidence is thin.`);
    if (r.summary.trades < 20) out.push("Fewer than 20 out-of-sample trades in total.");
    if (r.summary.traded && r.summary.profitable / r.summary.traded < 0.5) out.push("Most traded windows lost money.");
    return out;
  }, [r]);
  const lastBench = r?.equity?.at(-1)?.benchmark;
  return (
    <>
      <Workbench rail={w && (
        <Panel title="Window schedule" sub="re-discover → trade → liquidate → roll">
          <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Train (sessions)"><NumInput value={w.train_days} step={21} onChange={(v) => setW({ ...w, train_days: v })} /></Field>
            <Field label="Test (sessions)"><NumInput value={w.test_days} step={21} onChange={(v) => setW({ ...w, test_days: v })} /></Field>
            <Field label="Max pairs"><NumInput value={w.top_k} onChange={(v) => setW({ ...w, top_k: v })} /></Field>
            <Field label="Selection" className="col-span-2"><Segmented value={w.selection} onChange={(v) => setW({ ...w, selection: v })} options={SEL} /></Field>
            <div className="col-span-2"><Toggle checked={w.expanding} onChange={(v) => setW({ ...w, expanding: v })} label="Expanding train window" /></div>
          </div>
          <RunButton full loading={job.loading} onClick={() => job.run(async () => { res.setData(await api("/api/walkforward", { walkforward: w })); await refresh(); })}>Run walk-forward</RunButton>
          <ErrorNote error={job.error} />
          </div>
        </Panel>
      )}>
      {!r ? <Empty title="Walk-forward not run" desc="Discovery for every window runs in parallel and is cached, so re-runs with new strategy or cost settings are fast." /> : (
        <>
          <Headline items={[
            { label: "Out-of-sample return", value: fmt.spct(r.summary.return), tone: tone(r.summary.return), note: lastBench == null ? undefined : `SPY ${lastBench > 0 ? "+" : ""}${lastBench.toFixed(1)}% same period` },
            { label: "Out-of-sample Sharpe", value: fmt.num(r.summary.sharpe), tone: tone(r.summary.sharpe), note: "daily returns, annualised" },
            { label: "Profitable windows", value: `${r.summary.profitable}/${r.summary.traded}`, note: `of ${r.summary.windows} windows, ${r.summary.with_pairs} had pairs` },
            { label: "Out-of-sample trades", value: r.summary.trades, note: `final test from ${String(r.test_start).slice(0, 10)}` },
          ]} />
          <Warnings items={warns} />
          <Panel title="Stitched out-of-sample return" sub="% of starting capital; every point was traded with pairs chosen from earlier data only">
            <TimeChart data={r.equity} unit="%" height={300} series={[{ key: "strategy", color: PALETTE.brand, fill: true }]} />
          </Panel>
          <div className="grid gap-6 2xl:grid-cols-[1fr_1.4fr]">
            <Panel title="Return by window" sub="%">
              <Bars data={r.windows.map((x: any) => ({ window: `W${x.window}`, ret: +(x.return * 100).toFixed(3) }))} x="window" y="ret" height={260} />
            </Panel>
            <Panel title="Windows" bodyClass="p-0">
              <DataTable rows={r.windows} rowKey="window" maxH={300} dense cols={[
                { key: "window", label: "#", align: "right" }, { key: "test_start", label: "Test from", className: "num" },
                { key: "n_significant", label: "Sig.", align: "right" },
                { key: "pairs", label: "Pairs", className: "num max-w-56 truncate" },
                { key: "n_trades", label: "Trades", align: "right" },
                { key: "return", label: "Return", align: "right", fmt: (v) => <span className={v > 0 ? "text-pos" : v < 0 ? "text-neg" : ""}>{fmt.spct(v)}</span> },
                { key: "final_test", label: "Test", align: "right", fmt: (v) => (v ? <Tag tone="warn">final</Tag> : "") },
              ]} />
            </Panel>
          </div>
        </>
      )}
      </Workbench>
    </>
  );
}

function Splits() {
  const job = useJob();
  const [rows, setRows] = useState<any[] | null>(null);
  const [test, setTest] = useState(false);
  const [sel, setSel] = useState("fdr");
  return (
    <>
      <Workbench rail={
      <Panel title="Chronological segments" sub="discover on train → evaluate later segments">
        <div className="space-y-4">
          <Segmented value={sel} onChange={setSel} options={SEL} />
          <Toggle checked={test} onChange={setTest} label="Include final test (one-time)" />
          <RunButton full loading={job.loading} onClick={() => job.run(async () => setRows(await api("/api/splits", { selection: sel, include_test: test })))}>Evaluate</RunButton>
          <ErrorNote error={job.error} />
        </div>
      </Panel>}>
      {!rows && <Empty title="Not evaluated yet" desc="Compare in-sample, validation and (optionally) final-test results for one configuration. The final test refits discovery on train + validation." />}
      {rows && (
        <Panel title="Segment results" bodyClass="p-0">
          <DataTable rows={rows} rowKey="segment" cols={[
            { key: "segment", label: "Segment", className: "text-foreground" }, { key: "fit", label: "Fit", className: "num" }, { key: "eval", label: "Eval", className: "num" },
            { key: "pairs", label: "Pairs", className: "num" },
            { key: "total_return", label: "Return", align: "right", fmt: (v) => fmt.spct(v) }, { key: "sharpe", label: "Sharpe", align: "right", fmt: (v) => fmt.num(v) },
            { key: "max_drawdown", label: "Max DD", align: "right", fmt: (v) => fmt.pct(v) }, { key: "n_trades", label: "Trades", align: "right" },
          ]} />
        </Panel>
      )}
      </Workbench>
    </>
  );
}

function Grid() {
  const job = useJob();
  const [out, setOut] = useState<any>(null);
  const [sel, setSel] = useState("raw");
  const [p, setP] = useState({ entries: "1.5, 2, 2.5", exits: "0, 0.5", lookbacks: "40, 60", costs: "1, 2" });
  const nums = (s: string) => s.split(",").map((x) => parseFloat(x)).filter((x) => Number.isFinite(x));
  const heat = useMemo(() => {
    if (!out?.rows?.length) return null;
    const base = out.rows.filter((r: any) => r.cost_mult === Math.min(...out.rows.map((x: any) => x.cost_mult)));
    const E = [...new Set(base.map((r: any) => r.entry_z))].sort() as number[];
    const X = [...new Set(base.map((r: any) => r.exit_z))].sort() as number[];
    const m = E.map((e) => X.map((x) => {
      const v = base.filter((r: any) => r.entry_z === e && r.exit_z === x && r.sharpe !== null).map((r: any) => r.sharpe);
      return v.length ? v.reduce((a: number, b: number) => a + b, 0) / v.length : null;
    }));
    return { rows: E.map((e) => `entry ${e}`), cols: X.map((x) => `exit ${x}`), m };
  }, [out]);
  const sh = (out?.rows ?? []).map((r: any) => r.sharpe).filter((v: any) => v !== null);
  return (
    <>
      <Workbench rail={
      <Panel title="Parameter grid" sub="validation segment only — never the final test">
        <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {(["entries", "exits", "lookbacks", "costs"] as const).map((k) => (
            <Field key={k} label={{ entries: "Entry z", exits: "Exit z", lookbacks: "Lookbacks", costs: "Cost ×" }[k]}>
              <input value={p[k]} onChange={(e) => setP({ ...p, [k]: e.target.value })}
                className="num h-9 rounded-md border border-input bg-surface-2 px-3 text-[13px] outline-none focus:border-brand/60" />
            </Field>
          ))}
          <Field label="Pairs" className="col-span-2"><Segmented value={sel} onChange={setSel} options={[{ value: "fdr", label: "FDR" }, { value: "raw", label: "Raw p" }]} /></Field>
        </div>
        <RunButton full loading={job.loading} onClick={() => job.run(async () => setOut(await api("/api/robustness", {
          selection: sel, entries: nums(p.entries), exits: nums(p.exits), lookbacks: nums(p.lookbacks), costs: nums(p.costs) })))}>Run grid</RunButton>
        <ErrorNote error={job.error} />
        </div>
      </Panel>}>
      {!out && <Empty title="No grid yet" desc="Every variant tried counts toward selection bias — the best of many backtests is optimistic." />}
      {out && (out.note ? <Callout tone="warn">{out.note}</Callout> : (
        <>
          <KpiRow cols={5}>
            <Kpi label="Variants tested" value={out.rows.length} hint="all count toward selection bias" />
            <Kpi label="Positive Sharpe" value={`${sh.filter((v: number) => v > 0).length}/${sh.length}`} />
            <Kpi label="Median Sharpe" value={fmt.num(sh.length ? [...sh].sort((a: number, b: number) => a - b)[Math.floor(sh.length / 2)] : null)} />
            <Kpi label="Best Sharpe" value={fmt.num(sh.length ? Math.max(...sh) : null)} hint="optimistic: best of many" />
            <Kpi label="Worst Sharpe" value={fmt.num(sh.length ? Math.min(...sh) : null)} />
          </KpiRow>
          <div className="grid gap-6 2xl:grid-cols-[1fr_1.3fr]">
            {heat && <Panel title="Validation Sharpe" sub="mean over lookbacks, lowest cost"><Heatmap rows={heat.rows} cols={heat.cols} matrix={heat.m} /></Panel>}
            <Panel title="All variants" sub={`pairs: ${out.pairs.join(", ")}`} bodyClass="p-0">
              <DataTable rows={out.rows.map((r: any, i: number) => ({ ...r, id: i }))} rowKey="id" maxH={320} dense cols={[
                { key: "entry_z", label: "Entry", align: "right" }, { key: "exit_z", label: "Exit", align: "right" },
                { key: "lookback", label: "LB", align: "right" }, { key: "cost_mult", label: "Cost ×", align: "right" },
                { key: "total_return", label: "Return", align: "right", fmt: (v) => fmt.spct(v) },
                { key: "sharpe", label: "Sharpe", align: "right", fmt: (v) => <span className={v > 0 ? "text-pos" : v < 0 ? "text-neg" : ""}>{fmt.num(v)}</span> },
                { key: "n_trades", label: "Trades", align: "right" },
              ]} />
            </Panel>
          </div>
        </>
      ))}
      </Workbench>
    </>
  );
}

function ML() {
  const job = useJob();
  const [out, setOut] = useState<any>(null);
  const [p, setP] = useState({ horizon: 10, min_abs_z: 1, threshold: 0.5, n_pairs: 5, source: "top" });
  const s = out?.summary;
  return (
    <>
      <Workbench rail={
      <Panel title="Reversion classifier" sub="boosted trees · purged labels · fixed params">
        <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Horizon H"><NumInput value={p.horizon} onChange={(v) => setP({ ...p, horizon: v })} /></Field>
          <Field label="Min |z|"><NumInput value={p.min_abs_z} step={0.25} onChange={(v) => setP({ ...p, min_abs_z: v })} /></Field>
          <Field label="Prob. threshold"><NumInput value={p.threshold} step={0.05} onChange={(v) => setP({ ...p, threshold: v })} /></Field>
          <Field label="Pairs"><NumInput value={p.n_pairs} onChange={(v) => setP({ ...p, n_pairs: v })} /></Field>
          <Field label="Pair source" className="col-span-2"><Segmented value={p.source} onChange={(v) => setP({ ...p, source: v })} options={[{ value: "eligible", label: "FDR-eligible" }, { value: "top", label: "Top score" }]} /></Field>
        </div>
        <RunButton full loading={job.loading} onClick={() => job.run(async () => setOut(await api("/api/ml", p)))}>Train & evaluate</RunButton>
        <ErrorNote error={job.error} />
        </div>
      </Panel>}>
      {!out && <Empty title="Model not trained" desc="Predicts whether a stretched spread reverts within H sessions. Compared against a |z|-only baseline and the unfiltered strategy on validation." />}
      {out && (
        <>
          <KpiRow cols={6}>
            <Kpi label="Train rows" value={fmt.int(s.n_train)} />
            <Kpi label="Eval rows" value={fmt.int(s.n_eval)} hint={`base rate ${fmt.pct(s.eval_base_rate, 1)}`} />
            <Kpi label="AUC · model" value={fmt.num(s.auc_model, 3)} tone="brand" />
            <Kpi label="AUC · |z| baseline" value={fmt.num(s.auc_baseline_absz, 3)} />
            <Kpi label="Brier · model" value={fmt.num(s.brier_model, 4)} />
            <Kpi label="Brier · base rate" value={fmt.num(s.brier_base_rate, 4)} />
          </KpiRow>
          <Callout tone={(s.auc_model ?? 0) > (s.auc_baseline_absz ?? 0) ? "brand" : "warn"}>
            {(s.auc_model ?? 0) > (s.auc_baseline_absz ?? 0)
              ? "The model ranks reversions better than |z| alone on validation. Check below whether that survives costs."
              : "The model does not beat the |z| baseline out of sample. A sophisticated model that fails out of sample is not an improvement."}
          </Callout>
          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Strategy comparison · validation" bodyClass="p-0">
              <DataTable rows={out.comparison} rowKey="strategy" cols={[
                { key: "strategy", label: "Strategy", className: "text-foreground" },
                { key: "total_return", label: "Return", align: "right", fmt: (v) => fmt.spct(v) }, { key: "sharpe", label: "Sharpe", align: "right", fmt: (v) => fmt.num(v) },
                { key: "n_trades", label: "Trades", align: "right" }, { key: "win_rate", label: "Win", align: "right", fmt: (v) => fmt.pct(v, 0) },
              ]} />
            </Panel>
            <Panel title="Permutation importance" sub="drop in validation AUC" bodyClass="p-0">
              <DataTable rows={out.importance} rowKey="feature" dense cols={[
                { key: "feature", label: "Feature", className: "num text-foreground" },
                { key: "importance_mean", label: "Δ AUC", align: "right", fmt: (v) => fmt.num(v, 4) },
                { key: "importance_std", label: "± std", align: "right", fmt: (v) => fmt.num(v, 4) },
              ]} />
            </Panel>
          </div>
          <p className="text-[12px] text-muted-foreground">Pairs: <span className="num">{out.pairs.join(", ")}</span></p>
        </>
      )}
      </Workbench>
    </>
  );
}
