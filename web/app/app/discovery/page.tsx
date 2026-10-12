"use client";
import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { api, fmt } from "@/lib/api";
import { useJob, useResource, useStatus } from "@/components/qp/store";
import { Heatmap, PALETTE, TimeChart } from "@/components/qp/charts";
import {
  RailGroup, Workbench,
  Bool, Callout, DataTable, Empty, ErrorNote, Field, Headline, Kpi, KpiRow, NumInput, PageHeader, Panel, RunButton, Segmented, Tag, Toggle, Warnings,
} from "@/components/qp/ui";

export default function Discovery() {
  const { status, refresh } = useStatus();
  const res = useResource<any>("/api/discovery");
  const job = useJob();
  const [cfg, setCfg] = useState<any>(null);
  const [q, setQ] = useState("");
  const [show, setShow] = useState<"all" | "sig" | "elig">("all");
  const [sel, setSel] = useState<any>(null);
  const [pair, setPair] = useState<any>(null);
  const [corr, setCorr] = useState<any>(null);

  useEffect(() => { if (status && !cfg) setCfg(status.config.discovery); }, [status]);
  useEffect(() => { if (res.data?.rows?.length && !sel) setSel(res.data.rows[0]); }, [res.data]);
  useEffect(() => {
    if (!sel) return;
    api(`/api/pair?y=${sel.y}&x=${sel.x}`).then(setPair).catch(() => setPair(null));
  }, [sel?.pair, res.data]);
  useEffect(() => { if (res.data?.ran) api("/api/correlation").then(setCorr).catch(() => {}); }, [res.data]);

  const rows = useMemo(() => {
    let r = res.data?.rows ?? [];
    if (q) r = r.filter((x: any) => x.pair.includes(q.toUpperCase()));
    if (show === "sig") r = r.filter((x: any) => x.fdr_pass);
    if (show === "elig") r = r.filter((x: any) => x.eligible);
    return r;
  }, [res.data, q, show]);

  if (!status?.loaded) return (<><PageHeader eyebrow="Research · 01" title="Pair discovery" /><Empty title="No data loaded" desc="Load prices on the Overview or Data page first." /></>);
  const u = (k: string, v: any) => setCfg({ ...cfg, [k]: v });
  const d = res.data;

  const run = () => job.run(async () => {
    res.setData(await api("/api/discovery", { discovery: cfg }));
    setSel(null);
    await refresh();
  });

  return (
    <>
      <PageHeader eyebrow="Research · 01" title="Pair discovery"
        desc="Every unordered pair is tested with Engle–Granger on the training window. Benjamini–Hochberg controls the false-discovery rate across the whole family, so significance is judged on q, not p."
        right={d?.ran && <Tag tone="brand">window {d.window[0]} → {d.window[1]}</Tag>} />

      <Workbench rail={cfg && (
        <Panel title="Test configuration" sub="Computed on the training split">
          <div className="space-y-4">
          <RailGroup title="Significance">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Raw α"><NumInput value={cfg.coint_alpha} step={0.005} onChange={(v) => u("coint_alpha", v)} /></Field>
            <Field label="FDR q"><NumInput value={cfg.fdr_q} step={0.01} onChange={(v) => u("fdr_q", v)} /></Field>
          </div>
          </RailGroup>
          <RailGroup title="Eligibility">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Min observations"><NumInput value={cfg.min_obs} step={21} onChange={(v) => u("min_obs", v)} /></Field>
            <Field label="Max missing"><NumInput value={cfg.max_missing_frac} step={0.01} onChange={(v) => u("max_missing_frac", v)} /></Field>
            <Field label="Min half-life (d)"><NumInput value={cfg.min_half_life} step={0.5} onChange={(v) => u("min_half_life", v)} /></Field>
            <Field label="Max half-life (d)"><NumInput value={cfg.max_half_life} step={5} onChange={(v) => u("max_half_life", v)} /></Field>
            <Field label="Stability window"><NumInput value={cfg.stability_window} step={21} onChange={(v) => u("stability_window", v)} /></Field>
            <Field label="Intercept"><Toggle checked={cfg.use_intercept} onChange={(v) => u("use_intercept", v)} label="α term" /></Field>
          </div>
          </RailGroup>
          <RailGroup title="Model">
            <Segmented value={cfg.coint_trend} onChange={(v) => u("coint_trend", v)}
              options={[{ value: "c", label: "Constant" }, { value: "ct", label: "Constant + trend" }]} />
            <p className="num text-[11.5px] text-muted-foreground">{cfg.coint_trend === "c" ? "y = α + βx + ε" : "y = α + γt + βx + ε"}</p>
          </RailGroup>
          <RunButton full loading={job.loading} onClick={run}>Run discovery</RunButton>
          <ErrorNote error={job.error} />
          </div>
        </Panel>
      )}>

      {!d?.ran ? <Empty title="Discovery has not been run" desc="Configure the test above and run it. Results are computed on the training split only." /> : (
        <>
          <Headline items={[
            { label: "Pairs tested", value: d.n_tested, note: `${d.tickers.length} eligible tickers` },
            { label: "Raw p < α", value: d.n_raw, note: `~${(d.n_tested * d.alpha).toFixed(1)} expected by chance` },
            { label: "Survive FDR", value: d.n_significant, tone: d.n_significant ? "brand" : undefined, note: `BH q ≤ ${d.q}` },
            { label: "Tradeable", value: d.n_eligible, tone: d.n_eligible ? "pos" : undefined, note: "significant + usable half-life" },
          ]} />
          <KpiRow cols={6}>
            <Kpi label="Eligible tickers" value={d.tickers.length} hint={Object.keys(d.excluded).length ? `${Object.keys(d.excluded).length} excluded` : "none excluded"} />
            <Kpi label="Hit rate" value={fmt.pct(d.n_significant / Math.max(d.n_tested, 1), 1)} />
          </KpiRow>

          <Panel title="Candidate pairs" sub="Click a row for diagnostics · sortable"
            right={
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter e.g. KO"
                    className="h-8 w-40 rounded-md border border-input bg-surface-2 pl-8 pr-2 text-[12.5px] outline-none focus:border-brand/60" />
                </div>
                <Segmented value={show} onChange={setShow} options={[{ value: "all", label: "All" }, { value: "sig", label: "Significant" }, { value: "elig", label: "Eligible" }]} />
              </div>
            } bodyClass="p-0">
            <DataTable rows={rows} onRow={setSel} selected={sel?.pair} maxH={440} cols={[
              { key: "pair", label: "Pair", className: "num font-medium text-foreground" },
              { key: "n_obs", label: "Obs", align: "right" },
              { key: "return_corr", label: "Ret ρ", align: "right", fmt: (v) => fmt.num(v, 2) },
              { key: "beta", label: "β", align: "right", fmt: (v) => fmt.num(v, 3) },
              { key: "eg_stat", label: "EG t", align: "right", fmt: (v) => fmt.num(v, 2) },
              { key: "eg_pvalue", label: "p", align: "right", fmt: (v) => fmt.p(v) },
              { key: "q_value", label: "q (BH)", align: "right", fmt: (v, r) => <span className={r.fdr_pass ? "text-brand" : ""}>{fmt.p(v)}</span> },
              { key: "half_life", label: "Half-life", align: "right", fmt: (v) => (v == null ? "—" : `${fmt.num(v, 1)}d`) },
              { key: "beta_cv", label: "β CV", align: "right", fmt: (v) => fmt.num(v, 2) },
              { key: "score", label: "Score", align: "right", fmt: (v) => fmt.num(v, 3) },
              { key: "fdr_pass", label: "FDR", align: "right", fmt: (v) => <Bool v={v} /> },
              { key: "eligible", label: "Elig.", align: "right", fmt: (v) => <Bool v={v} /> },
            ]} />
          </Panel>

          {sel && pair && (
            <>
              <div className="flex items-center gap-3 pt-2">
                <h2 className="num text-[20px] font-medium">{sel.pair}</h2>
                {pair.stats.fdr_pass ? <Tag tone="brand">FDR significant</Tag> : <Tag>not significant</Tag>}
                {pair.stats.eligible && <Tag tone="pos">eligible</Tag>}
              </div>
              <KpiRow cols={7}>
                <Kpi label="Hedge β" value={fmt.num(pair.stats.beta, 3)} hint={`α ${fmt.num(pair.stats.intercept, 2)}`} />
                <Kpi label="EG p-value" value={fmt.p(pair.stats.eg_pvalue)} />
                <Kpi label="BH q-value" value={fmt.p(pair.stats.q_value)} tone={pair.stats.fdr_pass ? "brand" : undefined} />
                <Kpi label="ADF p (naive)" value={fmt.p(pair.stats.adf_pvalue_naive)} hint="descriptive only" />
                <Kpi label="Half-life" value={pair.stats.half_life == null ? "invalid" : `${fmt.num(pair.stats.half_life, 1)}d`} />
                <Kpi label="OU σ (eq.)" value={fmt.num(pair.ou.sigma_eq, 2)} hint={`θ ${fmt.num(pair.ou.theta, 3)}/d`} />
                <Kpi label="Rolling β CV" value={fmt.num(pair.stats.beta_cv, 2)} />
              </KpiRow>
              <Warnings items={pair.warnings} />
              <div className="grid gap-6 xl:grid-cols-2">
                <Panel title="Normalised prices" sub="start = 100, discovery window">
                  <TimeChart data={pair.prices} series={[{ key: sel.y, color: PALETTE.brand }, { key: sel.x, color: PALETTE.amber }]} />
                </Panel>
                <Panel title="Spread" sub="residual y − α − βx with ±2σ bands">
                  <TimeChart data={pair.spread} series={[{ key: "spread", color: PALETTE.brand, fill: true }, { key: "upper", color: PALETTE.neg }, { key: "mean", color: PALETTE.grey }, { key: "lower", color: PALETTE.neg }]} legend={false} />
                </Panel>
                <Panel title="Rolling z-score" sub={`lookback ${status.config.strategy.lookback} sessions, causal`}>
                  <TimeChart data={pair.z} series={[{ key: "z", color: PALETTE.violet }]} />
                </Panel>
                <Panel title="Hedge-ratio stability" sub="rolling OLS β vs full-window β">
                  <TimeChart data={pair.beta} series={[{ key: "rolling", color: PALETTE.teal }, { key: "static", color: PALETTE.grey }]} />
                </Panel>
              </div>
            </>
          )}

          {corr && (
            <Panel title="Return correlation matrix" sub="Correlation of log returns — not evidence of cointegration">
              <Heatmap labels={corr.tickers} matrix={corr.matrix} />
            </Panel>
          )}
          <Callout>
            Score = w₁·rank(−log₁₀ q) + w₂·rank(1/(1+CV of rolling β)) + w₃·rank(history). Pairs are never ranked by backtest profit.
          </Callout>
        </>
      )}
      </Workbench>
    </>
  );
}
