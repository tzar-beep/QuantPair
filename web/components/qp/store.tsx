"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";

type Ctx = { status: any; online: boolean | null; refresh: () => Promise<void>; setStatus: (s: any) => void };
const C = createContext<Ctx>({ status: null, online: null, refresh: async () => {}, setStatus: () => {} });

export function StatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<any>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const refresh = useCallback(async () => {
    try {
      setStatus(await api("/api/status"));
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  return <C.Provider value={{ status, online, refresh, setStatus }}>{children}</C.Provider>;
}

export const useStatus = () => useContext(C);

/** Run an API call with loading/error state. */
export function useJob<T = any>() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async (fn: () => Promise<T>): Promise<T | undefined> => {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, []);
  return { loading, error, run, setError };
}

/** GET a resource once on mount (server keeps results between pages). */
export function useResource<T = any>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    if (!path) return;
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  }, [path]);
  useEffect(() => { load(); }, [load]);
  return { data, setData, error, reload: load };
}
