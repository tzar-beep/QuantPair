import Link from "next/link";
import fig from "@/lib/figure1.json";
import { Globe } from "@/components/qp/globe";

const FINDINGS = [
  ["Default (ETFs + large caps)", 105, 0, 21, "+0.9%", "0.08"],
  ["Consumer staples", 45, 1, 26, "+6.3%", "0.54"],
  ["US banks", 36, 0, 2, "+0.7%", "0.50"],
  ["Energy", 36, 0, 13, "+3.5%", "0.40"],
  ["Utilities", 36, 0, 24, "+0.9%", "0.28"],
  ["Positive control", 21, 2, 31, "+0.4%", "0.04"],
] as const;

const STEPS = [
  ["Discover", "Engle–Granger on every pair, fitted on training data only."],
  ["Correct", "Benjamini–Hochberg keeps the false-discovery rate at 10%."],
  ["Trade", "Next-bar execution on both legs, with fees, slippage and borrow."],
  ["Validate", "Re-discover every six months; trade only the unseen window."],
];

/** Real walk-forward cumulative return (consumer staples) vs SPY on its own scale. */
function Figure() {
  const s = fig.series;
  const W = 640, H = 300, L = 40, R = 40, T = 12, B = 26;
  const sv = s.map((p) => p.s), bv = s.map((p) => p.b ?? 0);
  const sMin = Math.min(0, ...sv), sMax = Math.max(...sv), bMin = Math.min(0, ...bv), bMax = Math.max(...bv);
  const X = (i: number) => L + (i / (s.length - 1)) * (W - L - R);
  const Ys = (v: number) => T + (1 - (v - sMin) / (sMax - sMin)) * (H - T - B);
  const Yb = (v: number) => T + (1 - (v - bMin) / (bMax - bMin)) * (H - T - B);
  const line = (Y: (v: number) => number, v: number[]) => v.map((y, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(y).toFixed(1)}`).join(" ");
  const years = s.map((p, i) => [p.d.slice(0, 4), i] as const).filter(([y], i, a) => i === 0 || y !== a[i - 1][0]);
  const mono = "var(--font-geist-mono)";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Walk-forward cumulative return, consumer staples">
      {[0, sMax / 2, sMax].map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={Ys(v)} y2={Ys(v)} stroke={v === 0 ? "#CBD5E1" : "#EEF1F5"} />
          <text x={L - 8} y={Ys(v) + 4} textAnchor="end" fontSize="10.5" fill="#64748B" fontFamily={mono}>{v.toFixed(0)}%</text>
        </g>
      ))}
      <text x={W - R + 6} y={Yb(bMax) + 4} fontSize="10.5" fill="#94A3B8" fontFamily={mono}>{bMax.toFixed(0)}%</text>
      {years.filter((_, i) => i % 3 === 0).map(([y, i]) => (
        <text key={y} x={X(i)} y={H - 6} textAnchor="middle" fontSize="10.5" fill="#64748B" fontFamily={mono}>{y}</text>
      ))}
      <path d={line(Yb, bv)} fill="none" stroke="#CBD5E1" strokeWidth="1.2" />
      <path d={`${line(Ys, sv)} L${X(s.length - 1)},${Ys(0)} L${X(0)},${Ys(0)} Z`} fill="#0B2545" fillOpacity="0.06" />
      <path d={line(Ys, sv)} fill="none" stroke="#0B2545" strokeWidth="2" />
    </svg>
  );
}

export default function Landing() {
  return (
    <div className="paper min-h-screen text-[#111827]">
      <header className="border-b border-[#111827]/10 bg-[#F3F1EC]">
        <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between px-6">
          <Link href="/" className="serif text-[22px] font-semibold tracking-tight">QuantPair</Link>
          <nav className="flex items-center gap-8 text-[14px] text-[#475569]">
            <a href="#how" className="ulink hidden hover:text-[#111827] sm:inline">How it works</a>
            <a href="#results" className="ulink hidden hover:text-[#111827] sm:inline">Results</a>
            <Link href="/app" className="rounded-[3px] bg-[#0B2545] px-4 py-2 text-[13.5px] font-medium text-white hover:bg-[#13315C]">Open terminal</Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-[1180px] px-6">
        <section className="grid items-center gap-10 py-16 lg:grid-cols-[1fr_1fr] lg:py-20">
          <div>
            <div className="smallcaps">Statistical arbitrage research</div>
            <h1 className="display mt-5 text-[46px] sm:text-[60px]">Pairs research that survives the out-of-sample test.</h1>
            <p className="mt-6 max-w-md text-[17px] leading-relaxed text-[#475569]">
              Find cointegrated pairs, correct for false discoveries, and see whether the edge holds after costs on data the model never saw.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link href="/app" className="rounded-[3px] bg-[#0B2545] px-6 py-3 text-[15px] font-medium text-white hover:bg-[#13315C]">Open the terminal</Link>
              <a href="#results" className="rounded-[3px] border border-[#111827]/25 px-6 py-3 text-[15px] font-medium hover:border-[#111827]">See results</a>
            </div>
          </div>
          <div>
            <Globe />
            <p className="mt-2 text-center text-[12.5px] text-[#94A3B8]">Ten exchange cities, New York to Sydney</p>
          </div>
        </section>

        </main>
      <section className="bg-[#0B2545] text-white">
        <div className="mx-auto grid max-w-[1180px] grid-cols-2 gap-x-8 gap-y-8 px-6 py-14 md:grid-cols-4">
          {[["279", "pairs tested across six universes"], ["3", "survive false-discovery control"],
            [fig.sharpe.toFixed(2), "best out-of-sample Sharpe"], [String(fig.trades), "trades behind that result"]].map(([v, l]) => (
            <div key={l}>
              <div className="serif text-[48px] font-medium leading-none tracking-tight">{v}</div>
              <div className="mt-3 text-[14px] text-[#A9B8CF]">{l}</div>
            </div>
          ))}
        </div>
      </section>
      <main className="mx-auto max-w-[1180px] px-6">

        <section id="how" className="py-24">
          <h2 className="display text-[36px]">How it works</h2>
          <div className="mt-12 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(([t, d], i) => (
              <div key={t}>
                <div className="num text-[13px] text-[#94A3B8]">0{i + 1}</div>
                <div className="mt-3 text-[18px] font-semibold">{t}</div>
                <p className="mt-2 text-[15px] leading-relaxed text-[#64748B]">{d}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="results" className="pb-24">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <h2 className="display text-[36px]">Most pairs don&apos;t survive.</h2>
            <p className="max-w-sm text-[15px] text-[#64748B]">That is the finding, not a bug. Every result below is out of sample and after costs.</p>
          </div>
          <figure className="mt-10 rounded-[4px] border border-[#111827]/10 bg-[#FAF9F6] p-6 shadow-[0_1px_2px_rgb(17_24_39/0.04)]">
            <div className="flex items-baseline justify-between">
              <span className="text-[14px] font-semibold">Consumer staples · walk-forward</span>
              <span className="num text-[13px] text-[#0F9F75]">+{(fig.ret * 100).toFixed(1)}%</span>
            </div>
            <div className="mt-4"><Figure /></div>
            <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-[#64748B]">
              <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[#0B2545]" />Strategy, left axis</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[#CBD5E1]" />SPY, right axis</span>
              <span>Live data {fig.start.slice(0, 4)}–{fig.end.slice(0, 4)}</span>
            </figcaption>
          </figure>
          <div className="mt-10 overflow-x-auto">
            <table className="w-full min-w-[640px] text-[14.5px]">
              <thead>
                <tr className="border-b border-[#111827] text-left">
                  {["Universe", "Pairs tested", "Survive FDR", "Trades", "Return", "Sharpe"].map((h, i) => (
                    <th key={h} className={`pb-3 font-semibold ${i ? "text-right" : ""}`}>{h}</th>))}
                </tr>
              </thead>
              <tbody>
                {FINDINGS.map(([u, t, bh, tr, ret, sh]) => (
                  <tr key={u} className="border-b border-[#111827]/10">
                    <td className="py-3.5">{u}</td>
                    <td className="num py-3.5 text-right text-[#64748B]">{t}</td>
                    <td className="num py-3.5 text-right font-semibold">{bh}</td>
                    <td className="num py-3.5 text-right text-[#64748B]">{tr}</td>
                    <td className="num py-3.5 text-right">{ret}</td>
                    <td className="num py-3.5 text-right">{sh}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-[12.5px] text-[#94A3B8]">
            Walk-forward 2017–2026: 2-year training, 6-month test windows. Fees 1 bp + slippage 5 bp per leg, borrow 25 bp/yr.
            Close-to-close execution; survivorship bias not removed.
          </p>
        </section>

        <section className="flex flex-wrap items-center justify-between gap-6 border-t border-[#111827]/10 py-16">
          <p className="serif max-w-xl text-[26px] leading-snug">Change any assumption and rerun the study.</p>
          <Link href="/app" className="rounded-[3px] bg-[#0B2545] px-6 py-3 text-[15px] font-medium text-white hover:bg-[#13315C]">Open the terminal</Link>
        </section>
      </main>

      <footer className="bg-[#0B2545] text-[#A9B8CF]">
        <div className="mx-auto grid max-w-[1180px] gap-10 px-6 py-14 sm:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <div className="serif text-[22px] font-semibold text-white">QuantPair</div>
            <p className="mt-3 max-w-xs text-[13.5px] leading-relaxed">A research platform for cointegration-based statistical arbitrage, built to report negative results as honestly as positive ones.</p>
          </div>
          <div className="space-y-2.5 text-[13.5px]">
            <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-white/60">Research</div>
            <Link href="/app/discovery" className="ulink block w-fit hover:text-white">Pair discovery</Link>
            <Link href="/app/backtest" className="ulink block w-fit hover:text-white">Backtest</Link>
            <Link href="/app/validation" className="ulink block w-fit hover:text-white">Walk-forward</Link>
            <Link href="/app/live" className="ulink block w-fit hover:text-white">Live monitor</Link>
          </div>
          <div className="space-y-2.5 text-[13.5px]">
            <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-white/60">This page</div>
            <a href="#how" className="ulink block w-fit hover:text-white">How it works</a>
            <a href="#results" className="ulink block w-fit hover:text-white">Results</a>
            <Link href="/app/reports" className="ulink block w-fit hover:text-white">Reports &amp; exports</Link>
          </div>
        </div>
        <div className="border-t border-white/10">
          <div className="mx-auto flex max-w-[1180px] flex-wrap justify-between gap-3 px-6 py-5 text-[12px]">
            <span>Research software. Not investment advice. Past results do not guarantee future performance.</span>
            <span className="num">Data: Yahoo Finance · Alpaca · Finnhub</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
