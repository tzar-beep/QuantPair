"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Database, Play } from "lucide-react";
import { api, fmt, tone } from "@/lib/api";
import { useJob, useStatus } from "@/components/qp/store";
import { PageSkeleton, Workbench, Callout, ErrorNote, Headline, Kpi, KpiRow, PageHeader, Panel, RunButton, Tag } from "@/components/qp/ui";

const STAGES = [
  { href: "/app/discovery", t: "Pair discovery", d: "Engle–Granger + BH-FDR on the training window" },
  { href: "/app/strategy", t: "Strategy lab", d: "Spread, z-score and signal events for one pair" },
  { href: "/app/backtest", t: "Backtest", d: "Two-leg simulation with costs and capital limits" },
  { href: "/app/risk", t: "Risk", d: "VaR / ES, regimes, attribution and stress" },
  { href: "/app/validation", t: "Walk-forward", d: "Re-discovery out of sample, robustness, ML filter" },
  { href: "/app/reports", t: "Reports", d: "Markdown, CSV and JSON exports; experiment log" },
];

export default function Overview() {
  const { status, setStatus, online } = useStatus();
  const job = useJob();
  const [preset, setPreset] = useState("Default (ETFs + large caps)");

  const first = (source: "live" | "snapshot") => job.run(async () => {
    const body = source === "live" ? { source, universe: status?.presets?.[preset] } : { source };
    setStatus(await api("/api/data/load", body));
    await api("/api/backtest", { segment: "validation", selection: "fdr" });
    setStatus(await api("/api/status"));
  });

  if (!status) {
    return (
      <>
        <PageHeader eyebrow="Workspace" title="Research overview" />
        {online === false ? (
          <Callout tone="neg" title="Engine offline">
            Start the API: <span className="num text-foreground">.venv\Scripts\python -m uvicorn api.server:app --port 8000</span>
          </Callout>
        ) : <PageSkeleton />}
      </>
    );
  }

  const d = status.data, disc = status.discovery, bt = status.last_backtest, wf = status.walkforward;
  const m = bt?.metrics;
  return (
    <>
      <PageHeader eyebrow="Workspace" title="Research overview"
        desc="Data → discovery → signals → backtest → validation. Every number on this page is computed by the engine from the loaded prices."
        right={d ? <><Tag tone={d.is_snapshot ? "warn" : "pos"}>{d.is_snapshot ? "SNAPSHOT" : "LIVE"} · {d.retrieved_at.slice(0, 16)}</Tag></> : <Tag>NO DATA</Tag>} />

      {!d ? (
        <div className="grid gap-12 pt-2 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <div className="smallcaps">Begin a study</div>
            <h2 className="display mt-3 text-[32px]">Choose a universe and run the pipeline.</h2>
            <p className="mt-4 max-w-lg text-[15.5px] leading-relaxed text-[#334155]">
              The engine downloads adjusted daily closes, tests every pair on the training split, keeps only those that
              survive false-discovery control, and backtests them on the validation split.
            </p>
            <label className="mt-8 block text-[13px] font-medium text-[#111827]">Universe</label>
            <select value={preset} onChange={(e) => setPreset(e.target.value)}
              className="mt-2 h-11 w-full max-w-md rounded-[3px] border border-[#111827]/25 bg-white px-3 text-[14px] text-[#111827] outline-none focus:border-[#0B2545]">
              {Object.keys(status.presets ?? {}).map((p) => <option key={p}>{p}</option>)}
            </select>
            <p className="mt-2 text-[12.5px] text-[#64748B]">{(status.presets?.[preset] ?? []).join(" · ")}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <RunButton loading={job.loading} onClick={() => first("live")}><Play className="size-3.5" />Run with live data</RunButton>
              {status.snapshot && (
                <RunButton variant="outline" loading={job.loading} onClick={() => first("snapshot")}>
                  <Database className="size-3.5" />Use saved snapshot · {status.snapshot.retrieved_at.slice(0, 10)}
                </RunButton>
              )}
            </div>
            <div className="mt-4 max-w-lg"><ErrorNote error={job.error} /></div>
          </div>
          <ol className="divide-y divide-[#111827]/10 border-y border-[#111827]/10">
            {[["Validate data", "Gaps, duplicates and bad prints are reported, never interpolated."],
              ["Discover pairs", "Engle–Granger on every pair; Benjamini–Hochberg at q = 0.10."],
              ["Backtest survivors", "Next-bar execution, both legs, fees, slippage and borrow."],
              ["Read the verdict", "Most pairs fail. A cash result is a legitimate finding."]].map(([t, d], i) => (
              <li key={t} className="flex gap-5 py-5">
                <span className="serif text-[22px] text-[#94A3B8]">{i + 1}</span>
                <div><div className="text-[15px] font-semibold text-[#111827]">{t}</div><div className="mt-1 text-[14px] text-[#64748B]">{d}</div></div>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <Workbench rail={
          <Panel title="Experiment configuration" sub="Change in the relevant stage; saved with every exported experiment">
            <div className="num grid gap-y-2.5 text-[12.5px]">
              {[["Split", `${status.config.train_frac * 100}/${status.config.val_frac * 100}/${Math.round((1 - status.config.train_frac - status.config.val_frac) * 100)}`],
                ["α / q", `${status.config.discovery.coint_alpha} / ${status.config.discovery.fdr_q}`],
                ["Deterministic", status.config.discovery.coint_trend === "ct" ? "const + trend" : "constant"],
                ["Lookback", status.config.strategy.lookback], ["Entry / exit", `${status.config.strategy.entry_z} / ${status.config.strategy.exit_z}`],
                ["Stop / max hold", `${status.config.strategy.stop_z ?? "off"} / ${status.config.strategy.max_hold ?? "off"}`],
                ["Hedge", status.config.strategy.hedge_method], ["Costs", `${status.config.backtest.costs.fee_bps}+${status.config.backtest.costs.slippage_bps} bps`]].map(([k, v]) => (
                <div key={k as string} className="flex justify-between border-b border-line/60 pb-2"><span className="text-muted-foreground">{k}</span><span className="text-foreground">{v}</span></div>
              ))}
            </div>
          </Panel>}>
          <KpiRow cols={6}>
            <Kpi label="Symbols" value={d.tickers.length} hint={`${d.sessions.toLocaleString()} sessions`} />
            <Kpi label="Range" value={<span className="text-[15px]">{d.start.slice(0, 4)}–{d.end.slice(0, 4)}</span>} hint={`${d.start} → ${d.end}`} />
            <Kpi label="Pairs tested" value={disc?.n_tested ?? "—"} hint={disc ? `${disc.n_tickers} eligible tickers` : "run discovery"} />
            <Kpi label="BH-significant" value={disc?.n_significant ?? "—"} tone="brand" hint={`FDR q = ${status.config.discovery.fdr_q}`} />
            <Kpi label="Eligible pairs" value={disc?.n_eligible ?? "—"} tone="brand" hint="significant + half-life band" />
            <Kpi label="Data issues" value={`${d.errors} / ${d.warnings}`} tone={d.errors ? "neg" : undefined} hint="errors / warnings" />
          </KpiRow>

          <Panel title="Most recent backtest" sub={bt ? `${bt.segment} · selection on the training window` : undefined}
            right={<Link href="/app/backtest" className="text-[13px] text-[#0B2545] underline-offset-4 hover:underline">Open backtest →</Link>}>
            {m ? (
              <Headline items={[
                { label: "Total return", value: fmt.spct(m.total_return), tone: tone(m.total_return), note: `${m.n_trades} trades` },
                { label: "Sharpe ratio", value: fmt.num(m.sharpe), tone: tone(m.sharpe) },
                { label: "Max drawdown", value: fmt.pct(m.max_drawdown, 1), tone: "neg" },
                { label: "Net P&L", value: fmt.money(m.net_pnl), tone: tone(m.net_pnl), note: `after ${fmt.money(m.total_costs)} costs` },
              ]} />
            ) : <p className="text-[14px] text-[#64748B]">No backtest yet.</p>}
          </Panel>
          <Panel title="Out-of-sample validation"
            right={<Link href="/app/validation" className="text-[13px] text-[#0B2545] underline-offset-4 hover:underline">Open walk-forward →</Link>}>
            {wf ? (
              <Headline items={[
                { label: "Out-of-sample return", value: fmt.spct(wf.return), tone: tone(wf.return) },
                { label: "Trades", value: wf.trades },
                { label: "Windows", value: wf.windows },
                { label: "Verdict", value: wf.trades < 20 ? "Thin" : wf.return > 0 ? "Positive" : "Negative", tone: wf.trades < 20 ? "warn" : tone(wf.return), note: wf.trades < 20 ? "fewer than 20 trades" : undefined },
              ]} />
            ) : <p className="text-[14px] text-[#64748B]">Walk-forward not run — out-of-sample robustness is unassessed.</p>}
          </Panel>

          {disc && disc.n_eligible === 0 && (
            <Callout tone="warn" title="No tradeable cointegration in this universe">
              None of the {disc.n_tested} pairs passes the FDR threshold with a usable half-life on the training window, so the default strategy holds cash.
              That is a legitimate result. Try a sector-peer universe in Data, or the exploratory raw-p selection in Backtest.
            </Callout>
          )}

          <div>
            <div className="eyebrow mb-3">Research stages</div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {STAGES.map((s, i) => (
                <Link key={s.href} href={s.href} className="group rounded-xl border border-line bg-surface p-5 transition hover:border-brand/30 hover:bg-surface-2">
                  <div className="flex items-center justify-between">
                    <span className="num text-[11px] text-brand">0{i + 1}</span>
                    <ArrowUpRight className="size-4 text-muted-foreground transition group-hover:text-brand" />
                  </div>
                  <div className="mt-3 text-[14px] font-medium text-foreground">{s.t}</div>
                  <div className="mt-1 text-[12.5px] text-muted-foreground">{s.d}</div>
                </Link>
              ))}
            </div>
          </div>
        </Workbench>
      )}
    </>
  );
}
