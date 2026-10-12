"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { StatusProvider, useStatus } from "@/components/qp/store";

const NAV = [
  { href: "/app", label: "Overview" },
  { href: "/app/discovery", label: "Discovery" },
  { href: "/app/strategy", label: "Strategy" },
  { href: "/app/backtest", label: "Backtest" },
  { href: "/app/live", label: "Live" },
  { href: "/app/risk", label: "Risk" },
  { href: "/app/validation", label: "Walk-forward" },
  { href: "/app/reports", label: "Reports" },
  { href: "/app/data", label: "Data" },
];

function Masthead() {
  const path = usePathname();
  const { status, online } = useStatus();
  const d = status?.data, sp = status?.splits, disc = status?.discovery;
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);
  const current = NAV.find((n) => (n.href === "/app" ? path === "/app" : path.startsWith(n.href)))?.label ?? "Menu";
  return (
    <header className="sticky top-0 z-30 bg-[#0B2545] text-white shadow-[0_1px_0_rgb(0_0_0/0.2)]">
      <div className="mx-auto flex h-16 max-w-[1320px] items-center gap-8 px-6">
        <Link href="/" className="serif shrink-0 text-[22px] font-semibold tracking-tight text-white">QuantPair</Link>
        <nav className="hidden min-w-0 flex-1 gap-1 overflow-x-auto md:flex">
          {NAV.map(({ href, label }) => {
            const active = href === "/app" ? path === "/app" : path.startsWith(href);
            return (
              <Link key={href} href={href}
                className={cn("whitespace-nowrap px-3 py-5 text-[14px] transition",
                  active ? "font-semibold text-white shadow-[inset_0_-2px_0_0_#F2C063]" : "text-[#A9B8CF] hover:text-white")}>
                {label}
              </Link>
            );
          })}
        </nav>
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Open navigation"
          className="ml-auto flex items-center gap-2 rounded-[3px] border border-white/20 px-3 py-1.5 text-[14px] text-white md:hidden">
          {current}
          <svg viewBox="0 0 12 12" className={cn("size-3 transition-transform", open && "rotate-180")}><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
        </button>
        <span className="hidden shrink-0 items-center gap-2 text-[12.5px] text-[#A9B8CF] md:flex">
          <span className={cn("size-1.5 rounded-full", online ? "bg-[#0F9F75]" : online === false ? "bg-[#DC4545]" : "bg-[#B7791F]")} />
          {online === false ? "Engine offline" : d ? (d.is_snapshot ? "Snapshot data" : "Live data") : "No data"}
        </span>
      </div>
      {open && (
        <nav className="border-t border-white/10 bg-[#0B2545] px-6 pb-4 pt-2 md:hidden">
          {NAV.map(({ href, label }) => {
            const active = href === "/app" ? path === "/app" : path.startsWith(href);
            return (
              <Link key={href} href={href}
                className={cn("block border-b border-white/10 py-3 text-[15px] last:border-0", active ? "font-semibold text-white" : "text-[#A9B8CF]")}>
                {label}
              </Link>
            );
          })}
          <div className="pt-3 text-[12.5px] text-[#A9B8CF]">{online === false ? "Engine offline" : d ? `${d.is_snapshot ? "Snapshot" : "Live"} data · ${d.tickers.length} symbols` : "No data loaded"}</div>
        </nav>
      )}
      {(d || online === false) && (
        <div className="hidden border-t border-white/10 bg-[#0E2B50] md:block">
          <div className="num mx-auto flex max-w-[1320px] flex-wrap gap-x-6 gap-y-1 px-6 py-2 text-[11.5px] text-[#A9B8CF]">
            {online === false && <span className="text-[#DC4545]">Start the API: python -m uvicorn api.server:app --port 8000</span>}
            {d && <span>{d.tickers.length} symbols · {d.start} → {d.end}</span>}
            {sp && <span>train {sp.train[0]} → {sp.train[1]}</span>}
            {sp && <span>validation {sp.validation[0]} → {sp.validation[1]}</span>}
            {sp && <span className="text-[#F2C063]">test {sp.test[0]} → {sp.test[1]}</span>}
            {disc && <span>eligible pairs {disc.n_eligible}/{disc.n_tested}</span>}
          </div>
        </div>
      )}
    </header>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <StatusProvider>
      <div className="app-canvas min-h-screen">
        <Masthead />
        <main className="mx-auto max-w-[1320px] space-y-8 px-6 py-10">{children}</main>
      </div>
    </StatusProvider>
  );
}
