"use client";
import { Advanced, Field, NumInput, Segmented, Toggle, selectCls } from "@/components/qp/ui";

const fmtBps = (v: number) => `${v.toFixed(0)} bps`;

export type Strat = {
  lookback: number; entry_z: number; exit_z: number; stop_z: number | null; max_hold: number | null;
  hedge_method: string; hedge_window: number; kalman_delta: number;
};

export function StrategyFields({ s, set }: { s: Strat; set: (s: Strat) => void }) {
  const u = (k: keyof Strat, v: any) => set({ ...s, [k]: v });
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Z lookback"><NumInput value={s.lookback} step={5} onChange={(v) => u("lookback", v)} /></Field>
      <Field label="Entry |z|"><NumInput value={s.entry_z} step={0.1} onChange={(v) => u("entry_z", v)} /></Field>
      <Field label="Exit |z|"><NumInput value={s.exit_z} step={0.1} onChange={(v) => u("exit_z", v)} /></Field>
      <Field label="Hedge ratio" className="col-span-2">
        <select value={s.hedge_method} onChange={(e) => u("hedge_method", e.target.value)}
          className={selectCls}>
          <option value="static_ols">Static OLS</option><option value="rolling_ols">Rolling OLS</option><option value="kalman">Kalman filter</option>
        </select>
      </Field>
      <Advanced>
      <Field label="Stop |z|" hint="0 disables"><NumInput value={s.stop_z ?? 0} step={0.1} onChange={(v) => u("stop_z", v || null)} /></Field>
      <Field label="Max hold (days)" hint="0 disables"><NumInput value={s.max_hold ?? 0} step={5} onChange={(v) => u("max_hold", v || null)} /></Field>
      {s.hedge_method === "rolling_ols" && <Field label="Hedge window"><NumInput value={s.hedge_window} step={21} onChange={(v) => u("hedge_window", v)} /></Field>}
      {s.hedge_method === "kalman" && <Field label="Kalman δ"><NumInput value={s.kalman_delta} step={0.00005} onChange={(v) => u("kalman_delta", v)} /></Field>}
      </Advanced>
    </div>
  );
}

export type BT = { initial_capital: number; alloc_per_pair: number; max_gross_leverage: number; execution_lag: number;
  risk_free_rate: number; close_at_end: boolean; costs: { fee_bps: number; slippage_bps: number; borrow_bps_annual: number } };

export function BacktestFields({ b, set }: { b: BT; set: (b: BT) => void }) {
  const u = (k: keyof BT, v: any) => set({ ...b, [k]: v });
  const uc = (k: keyof BT["costs"], v: number) => set({ ...b, costs: { ...b.costs, [k]: v } });
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Capital ($)"><NumInput value={b.initial_capital} step={100000} onChange={(v) => u("initial_capital", v)} /></Field>
      <Field label="Fees (bps)"><NumInput value={b.costs.fee_bps} step={0.5} onChange={(v) => uc("fee_bps", v)} /></Field>
      <Field label="Slippage (bps)"><NumInput value={b.costs.slippage_bps} step={0.5} onChange={(v) => uc("slippage_bps", v)} /></Field>
      <Field label="Cost per round trip"><div className="num flex h-9 items-center text-[13.5px] text-[#475569]">{fmtBps(2 * (b.costs.fee_bps + b.costs.slippage_bps))} of gross notional</div></Field>
      <Advanced>
        <Field label="Alloc / pair" hint="gross, × equity"><NumInput value={b.alloc_per_pair} step={0.05} onChange={(v) => u("alloc_per_pair", v)} /></Field>
        <Field label="Max gross" hint="× equity"><NumInput value={b.max_gross_leverage} step={0.1} onChange={(v) => u("max_gross_leverage", v)} /></Field>
        <Field label="Execution lag" hint="sessions ≥ 1"><NumInput value={b.execution_lag} onChange={(v) => u("execution_lag", v)} /></Field>
        <Field label="Borrow (bps/yr)"><NumInput value={b.costs.borrow_bps_annual} step={5} onChange={(v) => uc("borrow_bps_annual", v)} /></Field>
        <Field label="Risk-free (ann.)"><NumInput value={b.risk_free_rate} step={0.005} onChange={(v) => u("risk_free_rate", v)} /></Field>
        <Field label="End of test"><Toggle checked={b.close_at_end} onChange={(v) => u("close_at_end", v)} label="Liquidate" /></Field>
      </Advanced>
    </div>
  );
}

export const SEGMENTS = [
  { value: "validation", label: "Validation" }, { value: "train", label: "In-sample" }, { value: "test", label: "Test" },
] as const;

export function SegmentPicker({ value, onChange }: { value: string; onChange: (v: any) => void }) {
  return <Segmented value={value} onChange={onChange} options={SEGMENTS as any} />;
}
