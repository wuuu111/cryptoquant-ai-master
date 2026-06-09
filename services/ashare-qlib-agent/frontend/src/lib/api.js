const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || "/api";
const API_CANDIDATES = Array.from(new Set([DEFAULT_API_BASE, "http://127.0.0.1:8710"]));

export function getDefaultApiBase() {
  return DEFAULT_API_BASE;
}

export async function apiRequest(path, options = {}, activeApiBase, setActiveApiBase = () => {}) {
  const failures = [];
  const candidates = Array.from(new Set([activeApiBase, ...API_CANDIDATES].filter(Boolean)));

  for (const base of candidates) {
    try {
      const response = await fetch(`${base}${path}`, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
      });
      if (!response.ok) {
        failures.push(`${base}: HTTP ${response.status}`);
        continue;
      }
      const payload = await response.json();
      setActiveApiBase(base);
      return payload;
    } catch (error) {
      failures.push(`${base}: ${error.message || "fetch failed"}`);
    }
  }

  throw new Error(failures.join(" | "));
}

export function fetchHealth(activeApiBase, setActiveApiBase) {
  return apiRequest("/health", {}, activeApiBase, setActiveApiBase);
}

export function fetchLatestCycle(activeApiBase, setActiveApiBase) {
  return apiRequest("/latest-cycle", {}, activeApiBase, setActiveApiBase);
}

export function fetchFundFeatures(activeApiBase, setActiveApiBase, limit = 12) {
  return apiRequest(`/fund-features?limit=${encodeURIComponent(limit)}`, {}, activeApiBase, setActiveApiBase);
}

export function fetchAccount(activeApiBase, setActiveApiBase) {
  return apiRequest("/account", {}, activeApiBase, setActiveApiBase);
}

export function saveAccount(body, activeApiBase, setActiveApiBase) {
  return apiRequest("/account", { method: "POST", body: JSON.stringify(body) }, activeApiBase, setActiveApiBase);
}

export function fetchPositions(activeApiBase, setActiveApiBase) {
  return apiRequest("/positions", {}, activeApiBase, setActiveApiBase);
}

export function fetchTrades(activeApiBase, setActiveApiBase, limit = 50) {
  return apiRequest(`/trades?limit=${encodeURIComponent(limit)}`, {}, activeApiBase, setActiveApiBase);
}

export function createTrade(body, activeApiBase, setActiveApiBase) {
  return apiRequest("/trades", { method: "POST", body: JSON.stringify(body) }, activeApiBase, setActiveApiBase);
}

export function applySuggestion(suggestionId, body, activeApiBase, setActiveApiBase) {
  return apiRequest(
    `/suggestions/${encodeURIComponent(suggestionId)}/apply`,
    { method: "POST", body: JSON.stringify(body || {}) },
    activeApiBase,
    setActiveApiBase,
  );
}

export function runSchedulerOnce(activeApiBase, setActiveApiBase) {
  return apiRequest("/scheduler/run-once", { method: "POST" }, activeApiBase, setActiveApiBase);
}
