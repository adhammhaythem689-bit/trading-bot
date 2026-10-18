import { useCallback, useEffect, useState } from "react";

// The repo is public, so the browser reads the files the GitHub Actions runs
// commit, straight from GitHub. No server, no laptop involvement.
export const GITHUB_BASE = "https://raw.githubusercontent.com/adhammhaythem689-bit/trading-bot/main";
export const DATA_BASE = import.meta.env.VITE_DATA_BASE || GITHUB_BASE;
export const IS_GITHUB_SOURCE = DATA_BASE === GITHUB_BASE;
export const POLL_MS = 2 * 60 * 1000;

async function getJson(path) {
  const res = await fetch(`${DATA_BASE}/${path}?t=${Date.now()}`, { cache: "no-store" });
  if (res.status === 404) return null; // file not created yet, not an error
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

export function useLiveData() {
  const [state, setState] = useState({
    hourly: null, daily: null, experiments: null, snapshot: null, fetchedAt: null, error: null, loading: true,
  });

  const load = useCallback(async () => {
    try {
      const [hourly, daily, experiments, snapshot] = await Promise.all([
        getJson("runlog/latest_hourly.json"),
        getJson("runlog/latest_daily.json"),
        getJson("runlog/latest_experiments.json"),
        getJson("city/public/city_data.json"),
      ]);
      setState({ hourly, daily, experiments, snapshot, fetchedAt: new Date().toISOString(), error: null, loading: false });
    } catch (e) {
      // keep the last good data on screen, but flag it
      setState((s) => ({ ...s, error: e.message, loading: false }));
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, POLL_MS);
    window.addEventListener("focus", load);
    return () => { clearInterval(timer); window.removeEventListener("focus", load); };
  }, [load]);

  return { ...state, reload: load };
}
