"use client";
import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { API, api, fmt, tone } from "@/lib/api";
import { useJob, useResource, useStatus } from "@/components/qp/store";
import { Bars, PALETTE, TimeChart } from "@/components/qp/charts";
import { BacktestFields, SegmentPicker, StrategyFields, type BT, type Strat } from "@/components/qp/forms";
import { RailGroup, Workbench, Callout, DataTable, Empty, ErrorNote, Field, Headline, Kpi, KpiRow, NumInput, PageHeader, Panel, RunButton, Segmented, Tag, Toggle, Warnings } from "@/components/qp/ui";

export default function Backtest() {
  const { status, refresh } = useStatus();
  const res = useResource<any>("/api/backtest");
  const disc = useResource<any>("/api/discovery");
  const job = useJob();
  const [s, setS] = useState<Strat | null>(null);
  const [b, setB] = useState<BT | null>(null);
  const [seg, setSeg] = useState("validation");
  const [sel, setSel] = useState("fdr");
  const [k, setK] = useState(5);
  const [manual, setManual] = useState<string[]>([]);
  const [bench, setBench] = useState(false);

  useEffect(() => { if (status && !s) { setS(status.config.strategy); setB(status.config.backtest); setK(status.config.walkforward.top_k); } }, [status]);
  if (!status?.loaded) return (<><PageHeader eyebrow="Research · 03" title="Backtest" /><Empty title="No data loaded" desc="Load prices first." /></>);

  const run = () => job.run(async () => {
    res.setData(await api("/api/backtest", { segment: seg, selection: sel, top_k: k, manual, strategy: s, backtest: b }));
    await refresh();
  });
  const r = res.data?.ran ? res.data : null;
  const m = r?.metrics;
  const benchRet = r?.equity?.length ? r.equity[r.equity.length - 1].benchmark : null;

  return (
    <>
      <PageHeader eyebrow="Research · 03" title="Backtest"
        desc="Pairs are selected on the fit window, then traded on the test period by a daily event-driven engine: signals at close t execute at close t+lag, both legs pay fees and slippage, shorts pay borrow."
        right={r && <>
          <Tag tone={r.in_sample ? "warn" : "pos"}>{r.in_sample ? "IN-SAMPLE" : "OUT-OF-SAMPLE"}</Tag>
          <Tag>{r.segment}</Tag>{r.selection === "raw" && <Tag tone="warn">RAW-p · exploratory</Tag>}
          <Tag>test {r.eval[0]} → {r.eval[1]}</Tag></>} />

      <Workbench rail={s && b && (
        <Panel title="Run configuration" sub="Select on fit window → trade test period">
          <div className="space-y-4">
          <RailGroup title="Universe & period">
            <Field label="Test period"><SegmentPicker value={seg} onChange={setSeg} /></Field>
            <Field label="Pair selection" hint={sel === "raw" ? "Exploratory — inflates false discoveries" : undefined}>
              <Segmented value={sel} onChange={setSel} options={[{ value: "fdr", label: "FDR" }, { value: "raw", label: "Raw p" }, { value: "manual", label: "Manual" }]} />
            </Field>
            <Field label="Max pairs (top-k)"><NumInput value={k} onChange={setK} /></Field>
          {sel === "manual" && (
            <div className="flex max-h-32 flex-wrap gap-1.5 overflow-auto">
              {(disc.data?.rows ?? []).map((row: any) => {
                const on = manual.includes(row.pair);
                return (
                  <button key={row.pair} type="button" onClick={() => setManual(on ? manual.filter((p) => p !== row.pair) : [...manual, row.pair])}
                    className={`num rounded-md border px-2 py-1 text-[11.5px] transition ${on ? "border-brand/50 bg-brand/15 text-brand" : "border-line text-muted-foreground hover:text-foreground"}`}>
                    {row.pair}
                  </button>
                );
              })}
            </div>
          )}
          {seg === "test" && <Callout tone="warn">Final test: view once, after freezing parameters on validation.</Callout>}
          </RailGroup>
          <RailGroup title="Strategy"><StrategyFields s={s} set={setS} /></RailGroup>
          <RailGroup title="Portfolio & costs"><BacktestFields b={b} set={setB} /></RailGroup>
          <RunButton full loading={job.loading} onClick={run}>Run backtest</RunButton>
          <ErrorNote error={job.error} />
          </div>
        </Panel>
      )}>

      {!r ? <Empty title="No backtest yet" desc="Configure the run above." /> : (
        <>
          <div className="text-[13px] text-muted-foreground">Pairs traded: <span className="num text-foreground">{r.pairs.length ? r.pairs.join(", ") : "none"}</span></div>
          {!r.pairs.length && <Callout tone="brand">No pairs passed the selection rule on the fit window, so the strategy held cash. That is a legitimate research outcome, not an error.</Callout>}
          <Headline items={[
            { label: "Total return", value: fmt.spct(m.total_return), tone: tone(m.total_return), note: `SPY ${benchRet == null ? "—" : `${benchRet > 0 ? "+" : ""}${benchRet.toFixed(1)}%`} same period` },
            { label: "Sharpe ratio", value: fmt.num(m.sharpe), tone: tone(m.sharpe), note: `Sortino ${fmt.num(m.sortino)}` },
            { label: "Max drawdown", value: fmt.pct(m.max_drawdown, 1), tone: "neg", note: `Calmar ${fmt.num(m.calmar)}` },
            { label: "Net P&L", value: fmt.money(m.net_pnl), tone: tone(m.net_pnl), note: `${fmt.money(m.gross_pnl)} gross − ${fmt.money(m.total_costs)} costs` },
          ]} />
          <KpiRow>
            <Kpi label="CAGR" value={fmt.spct(m.cagr)} tone={tone(m.cagr)} />
            <Kpi label="Volatility" value={fmt.pct(m.ann_vol)} />
            <Kpi label="Trades" value={m.n_trades} />
            <Kpi label="Win rate" value={fmt.pct(m.win_rate, 1)} />
            <Kpi label="Profit factor" value={fmt.num(m.profit_factor)} />
            <Kpi label="Avg trade" value={fmt.spct(m.avg_trade_return)} tone={tone(m.avg_trade_return)} />
            <Kpi label="Avg hold" value={m.avg_holding_days == null ? "—" : `${fmt.num(m.avg_holding_days, 1)}d`} />
            <Kpi label="Turnover" value={m.turnover == null ? "—" : `${fmt.num(m.turnover, 1)}× / yr`} />
            <Kpi label="Time in market" value={fmt.pct(m.time_in_market, 1)} />
            <Kpi label="Gross exposure" value={fmt.pct(m.avg_gross_exposure, 1)} />
            <Kpi label="Skipped entries" value={m.skipped_entries} />
          </KpiRow>
          <Warnings items={r.warnings} />

          <Panel title="Cumulative return" sub="% of starting capital · net vs gross of costs"
            right={<Toggle checked={bench} onChange={setBench} label="Show SPY" />}>
            <TimeChart data={r.equity} unit="%" height={320} series={[
              { key: "net", color: PALETTE.brand, fill: true }, { key: "gross", color: PALETTE.amber },
              ...(bench ? [{ key: "benchmark", color: PALETTE.grey }] : [])]} />
            {bench && <p className="mt-2 text-[12px] text-muted-foreground">SPY is a market benchmark, not a risk-matched comparison for a market-neutral strategy.</p>}
          </Panel>
          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Drawdown" sub="% below running peak">
              <TimeChart data={r.drawdown} unit="%" height={220} series={[{ key: "drawdown", color: PALETTE.neg, fill: true }]} />
            </Panel>
            <Panel title="Daily return distribution" sub="active days, %">
              <Bars data={r.histogram} x="bin" y="count" height={244} />
            </Panel>
          </div>
          {r.cum_pair.length > 0 && (
            <Panel title="Cumulative net P&L by pair" sub="$, after costs">
              <TimeChart data={r.cum_pair} height={260} series={r.pairs.map((p: string) => ({ key: p }))} />
            </Panel>
          )}
          <Panel title="Trade ledger" sub={`${r.trades.length} trades`} bodyClass="p-0"
            right={<a href={`${API}/api/export/trades.csv`} className="inline-flex items-center gap-1.5 text-[12px] text-brand hover:underline"><Download className="size-3.5" />CSV</a>}>
            <DataTable rows={r.trades} rowKey="entry_date" maxH={380} dense cols={[
              { key: "pair", label: "Pair", className: "num text-foreground" },
              { key: "direction", label: "Side", fmt: (v) => <span className={v === "long_spread" ? "text-pos" : "text-neg"}>{v === "long_spread" ? "Long" : "Short"}</span> },
              { key: "entry_date", label: "Entry", className: "num" }, { key: "exit_date", label: "Exit", className: "num" },
              { key: "exit_reason", label: "Reason" },
              { key: "entry_z", label: "z in", align: "right", fmt: (v) => fmt.num(v, 2) },
              { key: "holding_days", label: "Days", align: "right" },
              { key: "gross_pnl", label: "Gross", align: "right", fmt: (v) => fmt.money(v) },
              { key: "costs", label: "Costs", align: "right", fmt: (v, row) => fmt.money(v + row.borrow) },
              { key: "net_pnl", label: "Net", align: "right", fmt: (v) => <span className={v >= 0 ? "text-pos" : "text-neg"}>{fmt.money(v)}</span> },
              { key: "return_on_notional", label: "Ret", align: "right", fmt: (v) => fmt.spct(v) },
            ]} />
          </Panel>
        </>
      )}
      </Workbench>
    </>
  );
}
