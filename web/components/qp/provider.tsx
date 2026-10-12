"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useJob } from "@/components/qp/store";
import { Callout, ErrorNote, Field, Panel, RunButton, Segmented, Toggle } from "@/components/qp/ui";

export type Source = "live" | "alpaca";

const inputCls = "h-9 w-full rounded-[3px] border border-[#111827]/20 bg-[#FAF9F6] px-2.5 text-[13.5px] text-[#111827] outline-none focus:border-[#0B2545]";

/** Choose the history source and manage provider API keys (kept server-side, shown masked). */
export function ProviderPanel({ source, setSource }: { source: Source; setSource: (s: Source) => void }) {
  const [st, setSt] = useState<any>(null);
  const [form, setForm] = useState({ alpaca_key_id: "", alpaca_secret: "", finnhub_key: "" });
  const [persist, setPersist] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const job = useJob();
  useEffect(() => { api("/api/providers").then(setSt).catch(() => {}); }, []);

  const save = () => job.run(async () => {
    const body: Record<string, any> = { persist };
    for (const [k, v] of Object.entries(form)) if (v.trim()) body[k] = v.trim();
    setSt(await api("/api/providers/keys", body));
    setForm({ alpaca_key_id: "", alpaca_secret: "", finnhub_key: "" });
    setMsg(persist ? "Keys saved on the server (.env, gitignored)." : "Keys set for this session only.");
  });
  const test = (provider: string) => job.run(async () => {
    const r = await api("/api/providers/test", { provider });
    setMsg(`${provider === "alpaca" ? "Alpaca" : "Finnhub"} connected · SPY ${r.spy} at ${String(r.time).slice(11, 19)} UTC`);
  });

  return (
    <Panel title="Data provider" sub="Keys stay on the server and are never sent back to the browser">
      <div className="space-y-4">
        <Field label="Daily history from">
          <Segmented value={source} onChange={setSource} options={[{ value: "live", label: "Yahoo (no key)" }, { value: "alpaca", label: "Alpaca" }]} />
        </Field>
        <div className="space-y-1 text-[12.5px] text-[#475569]">
          <div className="flex justify-between"><span>Alpaca</span>
            <span className={st?.alpaca?.configured ? "text-[#0F9F75]" : "text-[#94A3B8]"}>{st?.alpaca?.configured ? `connected ${st.alpaca.key_id}` : "no key"}</span></div>
          <div className="flex justify-between"><span>Finnhub</span>
            <span className={st?.finnhub?.configured ? "text-[#0F9F75]" : "text-[#94A3B8]"}>{st?.finnhub?.configured ? `connected ${st.finnhub.key}` : "no key"}</span></div>
        </div>
        <details className="group border-t border-[#111827]/10 pt-3">
          <summary className="cursor-pointer list-none text-[13px] text-[#0B2545] hover:underline [&::-webkit-details-marker]:hidden">
            {st?.alpaca?.configured || st?.finnhub?.configured ? "Update API keys" : "Add API keys"}
          </summary>
          <div className="mt-3 space-y-3">
            <Field label="Alpaca key ID"><input autoComplete="off" value={form.alpaca_key_id} onChange={(e) => setForm({ ...form, alpaca_key_id: e.target.value })} className={inputCls} /></Field>
            <Field label="Alpaca secret"><input type="password" autoComplete="off" value={form.alpaca_secret} onChange={(e) => setForm({ ...form, alpaca_secret: e.target.value })} className={inputCls} /></Field>
            <Field label="Finnhub key" hint="optional, live quotes only"><input type="password" autoComplete="off" value={form.finnhub_key} onChange={(e) => setForm({ ...form, finnhub_key: e.target.value })} className={inputCls} /></Field>
            <Toggle checked={persist} onChange={setPersist} label="Remember on this machine" />
            <RunButton full loading={job.loading} onClick={save}>Save keys</RunButton>
            <p className="text-[12px] leading-relaxed text-[#94A3B8]">
              Free keys: alpaca.markets (history + real-time IEX quotes) and finnhub.io (real-time quotes).
            </p>
          </div>
        </details>
        {(st?.alpaca?.configured || st?.finnhub?.configured) && (
          <div className="flex gap-2">
            {st?.alpaca?.configured && <RunButton variant="outline" loading={job.loading} onClick={() => test("alpaca")}>Test Alpaca</RunButton>}
            {st?.finnhub?.configured && <RunButton variant="outline" loading={job.loading} onClick={() => test("finnhub")}>Test Finnhub</RunButton>}
          </div>
        )}
        <ErrorNote error={job.error} />
        {msg && !job.error && <Callout tone="pos">{msg}</Callout>}
      </div>
    </Panel>
  );
}
