"use client";
import { useEffect, useState } from "react";
import { api, fmt } from "@/lib/api";
import { useJob } from "@/components/qp/store";
import { PALETTE, TimeChart } from "@/components/qp/charts";
import { PageSkeleton, Workbench, Callout, DataTable, Empty, ErrorNote, Field, Headline, Kpi, KpiRow, NumInput, PageHeader, Panel, RunButton, Segmented } from "@/components/qp/ui";

export default function Risk() {
  const [level, setLevel] = useState("0.95");
  const [win, setWin] = useState(0);
  const [roll, setRoll] = useState(63);
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const job = useJob();
  const load = () => api(`/api/risk?level=${level}&window=${win}&roll=${roll}`).then((x) => { setD(x); setErr(null); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [level]);

  if (err && !d) return (<><PageHeader eyebrow="Validation · 04" title="Risk analytics" /><Empty title="Nothing to analyse" desc={err} /></>);
  if (!d) return <PageSkeleton />;
  const v = d.var, t = d.tail ?? {};
  return (
    <>
      <PageHeader eyebrow="Validation · 04" title="Risk analytics"
        desc="Tail risk, exposure, attribution, regimes and hypothetical stress for the most recent backtest. Scenarios are what-if calculations, not forecasts."
 />
      <Workbench rail={
        <Panel title="Risk settings" sub="historical simulation on daily equity returns">
          <div className="space-y-4">
            <Field label="Confidence level">
              <Segmented value={level} onChange={setLevel} options={["0.9", "0.95", "0.975", "0.99"].map((x) => ({ value: x, label: `${(+x * 100).toFixed(1)}%` }))} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="VaR window" hint="0 = full sample"><NumInput value={win} step={21} onChange={setWin} /></Field>
              <Field label="Rolling window"><NumInput value={roll} step={21} onChange={setRoll} /></Field>
            </div>
            <RunButton full onClick={load}>Apply</RunButton>
            <p className="border-t border-line pt-4 text-[12px] leading-relaxed text-muted-foreground">
              Losses are positive fractions of equity. Flat days are included, which lowers VaR for a strategy that is often in cash.
            </p>
          </div>
        </Panel>}>

      <Headline items={[
        { label: `1-day VaR ${(v.level * 100).toFixed(1)}%`, value: fmt.pct(v.var), tone: "neg", note: `${v.n} daily returns` },
        { label: `Expected shortfall`, value: fmt.pct(v.es), tone: "neg", note: "mean loss beyond VaR" },
        { label: "Worst day", value: fmt.pct(t.worst_day), tone: "neg" },
        { label: "Max drawdown", value: fmt.pct(d.max_drawdown, 1), tone: "neg" },
      ]} />
      <KpiRow cols={7}>
        <Kpi label="Best day" value={fmt.pct(t.best_day)} tone="pos" />
        <Kpi label="Skew" value={fmt.num(t.skew)} />
        <Kpi label="Excess kurtosis" value={fmt.num(t.excess_kurtosis)} />
        <Kpi label="Days < −2σ" value={t.days_below_2sd ?? "—"} hint={`normal ≈ ${fmt.num(t.expected_under_normal, 0)}`} />
      </KpiRow>

      <div className="grid gap-6 2xl:grid-cols-2">
        <Panel title="Drawdown" sub="% below running peak"><TimeChart data={d.drawdown} unit="%" height={220} series={[{ key: "drawdown", color: PALETTE.neg, fill: true }]} /></Panel>
        <Panel title="Rolling volatility" sub={`annualised %, ${roll}-day window`}><TimeChart data={d.rolling} unit="%" height={220} series={[{ key: "vol", color: PALETTE.brand, fill: true }]} /></Panel>
        <Panel title="Rolling Sharpe" sub={`${roll}-day window`}><TimeChart data={d.rolling} height={220} series={[{ key: "sharpe", color: PALETTE.violet }]} /></Panel>
        <Panel title="Exposure" sub="% of equity · gross, net and largest pair share">
          <TimeChart data={d.exposure} unit="%" height={220} series={[{ key: "gross", color: PALETTE.brand, fill: true }, { key: "net", color: PALETTE.amber }, { key: "max_pair_share", color: PALETTE.teal }]} />
        </Panel>
      </div>

      <div className="grid gap-6 2xl:grid-cols-[1fr_1fr]">
        <Panel title="Cost drag" sub="cumulative fees, slippage and borrow ($)">
          <TimeChart data={d.costs} height={220} series={[{ key: "fees", color: PALETTE.brand }, { key: "slippage", color: PALETTE.amber }, { key: "borrow", color: PALETTE.violet }]} />
        </Panel>
        <Panel title="Pair attribution" sub="gross, costs, net and share of losses" bodyClass="p-0">
          <DataTable rows={d.attribution} maxH={280} dense cols={[
            { key: "pair", label: "Pair", className: "num text-foreground" },
            { key: "gross_pnl", label: "Gross", align: "right", fmt: fmt.money }, { key: "costs", label: "Costs", align: "right", fmt: fmt.money },
            { key: "net_pnl", label: "Net", align: "right", fmt: (x) => <span className={x >= 0 ? "text-pos" : "text-neg"}>{fmt.money(x)}</span> },
            { key: "share_of_losses", label: "Loss share", align: "right", fmt: (x) => fmt.pct(x, 0) },
          ]} />
        </Panel>
      </div>

      <Panel title="Volatility regimes" sub="SPY 63-day realised vol vs its expanding median · regime known at the prior close" bodyClass="p-0">
        <DataTable rows={d.regimes} rowKey="regime" dense cols={[
          { key: "regime", label: "Regime", className: "text-foreground" }, { key: "days", label: "Days", align: "right" },
          { key: "active_days", label: "Active", align: "right" }, { key: "ann_return", label: "Ann. return", align: "right", fmt: (x) => fmt.spct(x) },
          { key: "ann_vol", label: "Ann. vol", align: "right", fmt: (x) => fmt.pct(x) }, { key: "sharpe", label: "Sharpe", align: "right", fmt: (x) => fmt.num(x) },
          { key: "hit_rate", label: "Hit rate", align: "right", fmt: (x) => fmt.pct(x, 1) },
          { key: "total_contribution", label: "Contribution", align: "right", fmt: (x) => fmt.spct(x) },
        ]} />
      </Panel>

      <div className="grid gap-6 2xl:grid-cols-2">
        <Panel title="Stress scenarios" sub="hypothetical loss on one long-spread position" bodyClass="p-0">
          {d.scenarios.length ? (
            <DataTable rows={d.scenarios} rowKey="assumption" maxH={300} dense cols={[
              { key: "pair", label: "Pair", className: "num text-foreground" }, { key: "scenario", label: "Scenario" },
              { key: "loss", label: "Loss", align: "right", fmt: (x) => <span className="text-neg">{fmt.money(x)}</span> },
              { key: "loss_pct_of_budget", label: "% budget", align: "right", fmt: (x) => fmt.pct(x) },
            ]} />
          ) : <div className="p-5 text-[13px] text-muted-foreground">No positions in this backtest.</div>}
        </Panel>
        <Panel title="Cost & volatility stress" right={<RunButton variant="outline" loading={job.loading}
          onClick={() => job.run(async () => { await api("/api/risk/cost-stress", { multipliers: [1, 2, 3, 5] }); await load(); })}>Re-run with 1×–5× costs</RunButton>}>
          <div className="space-y-4">
            {d.cost_stress && <DataTable rows={d.cost_stress} rowKey="cost_multiplier" dense cols={[
              { key: "cost_multiplier", label: "Costs ×", align: "right" }, { key: "total_return", label: "Return", align: "right", fmt: (x) => fmt.spct(x) },
              { key: "sharpe", label: "Sharpe", align: "right", fmt: (x) => fmt.num(x) }, { key: "total_costs", label: "Costs", align: "right", fmt: fmt.money },
            ]} />}
            <DataTable rows={d.vol_stress} rowKey="vol_factor" dense cols={[
              { key: "vol_factor", label: "Vol ×", align: "right" }, { key: "var", label: "VaR", align: "right", fmt: (x) => fmt.pct(x) },
              { key: "es", label: "ES", align: "right", fmt: (x) => fmt.pct(x) },
            ]} />
            <ErrorNote error={job.error} />
          </div>
        </Panel>
      </div>
      <Callout title="How a cointegrated pair still loses money">
        Relationships break (mergers, regulation, business change); spreads diverge further before converging; stale hedge ratios leave directional
        exposure; slow reversion accrues borrow; small edges vanish after costs; and some “discoveries” are chance — hence FDR control.
      </Callout>
      </Workbench>
    </>
  );
}
