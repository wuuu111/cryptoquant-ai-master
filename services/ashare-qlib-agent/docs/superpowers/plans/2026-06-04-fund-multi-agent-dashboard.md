# Fund Multi-Agent Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the frontend into a fund-first personal decision dashboard that prioritizes today's rebalance action while preserving layered multi-agent collaboration visibility.

**Architecture:** Replace the stock-era single-file dashboard assumptions with a fund-specific shell, typed data normalization layer, and two-page workspace: Today Recommendation and My Fund Portfolio. Keep the existing editorial workbench visual language, but remap all data flow to `health`, `latest-cycle`, `fund-features`, `scheduler/run-once`, and `holdings`.

**Tech Stack:** React 19, Vite, lucide-react, recharts, Vitest, Testing Library, existing FastAPI/HTTP fund endpoints

---

## File Structure

- Create: `services/ashare-qlib-agent/frontend/src/lib/api.js`
  - Single API client with candidate base URLs and JSON fetch helpers.
- Create: `services/ashare-qlib-agent/frontend/src/lib/fundDashboard.js`
  - Normalize backend payloads into UI-friendly shapes.
- Create: `services/ashare-qlib-agent/frontend/src/components/AppShell.jsx`
  - Brand, nav, API indicator, refresh action, status badges.
- Create: `services/ashare-qlib-agent/frontend/src/components/DecisionHero.jsx`
  - First-screen decision summary and primary metrics.
- Create: `services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.jsx`
  - Suggestion list with amount-first cards and expandable weight/reason details.
- Create: `services/ashare-qlib-agent/frontend/src/components/AgentDecisionChain.jsx`
  - Compact key-agent verdict chain.
- Create: `services/ashare-qlib-agent/frontend/src/components/RiskReviewPanel.jsx`
  - Review summary and risk note presentation.
- Create: `services/ashare-qlib-agent/frontend/src/components/FundRankingPanel.jsx`
  - Candidate ranking preview from `fund-features`.
- Create: `services/ashare-qlib-agent/frontend/src/components/PortfolioCompareTable.jsx`
  - Holdings vs target comparison table.
- Create: `services/ashare-qlib-agent/frontend/src/components/AgentTimeline.jsx`
  - Full agent trace, collaboration events, and messages.
- Create: `services/ashare-qlib-agent/frontend/src/components/EmptyState.jsx`
  - Reusable actionable empty-state panel.
- Create: `services/ashare-qlib-agent/frontend/src/test/setup.js`
  - DOM test setup.
- Create: `services/ashare-qlib-agent/frontend/src/lib/fundDashboard.test.jsx`
  - Unit tests for normalization helpers.
- Create: `services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.test.jsx`
  - UI test for amount-first rendering and blocked-state labels.
- Create: `services/ashare-qlib-agent/frontend/src/components/AppShell.test.jsx`
  - UI test for navigation and refresh state.
- Create: `services/ashare-qlib-agent/frontend/vitest.config.js`
  - Vitest config for jsdom.
- Modify: `services/ashare-qlib-agent/frontend/src/main.jsx`
  - Replace monolithic stock-era implementation with fund-first page composition.
- Modify: `services/ashare-qlib-agent/frontend/src/styles.css`
  - Preserve existing visual language while adding new fund-page sections.
- Modify: `services/ashare-qlib-agent/frontend/package.json`
  - Add `test` script and frontend test dependencies.
- Modify: `services/ashare-qlib-agent/frontend/index.html`
  - Update title to fund dashboard branding.
- Modify: `services/ashare-qlib-agent/README.md`
  - Document frontend run/build behavior if needed after refactor.

---

### Task 1: Establish Fund Frontend Data Layer And Test Harness

**Files:**
- Create: `services/ashare-qlib-agent/frontend/src/lib/api.js`
- Create: `services/ashare-qlib-agent/frontend/src/lib/fundDashboard.js`
- Create: `services/ashare-qlib-agent/frontend/src/lib/fundDashboard.test.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/test/setup.js`
- Create: `services/ashare-qlib-agent/frontend/vitest.config.js`
- Modify: `services/ashare-qlib-agent/frontend/package.json`

- [ ] **Step 1: Write the failing normalization test**

```jsx
import { describe, expect, it } from "vitest";
import {
  normalizeCyclePayload,
  normalizeFundFeaturesPayload,
  summarizeDecision,
} from "./fundDashboard";

describe("fund dashboard normalization", () => {
  it("builds amount-first suggestion cards and compact agent chain", () => {
    const cycle = normalizeCyclePayload({
      cycle_id: "fund_1",
      market: { regime: "RANGE", gate: "ALLOW_FULL", score: 0.01, exposure_multiplier: 0.85 },
      suggestions: [
        {
          symbol: "159915",
          action: "INCREASE",
          delta_value: 200000,
          current_weight: 0,
          target_weight: 0.2,
          delta_weight: 0.2,
          blocked: true,
          reason: "Purchase status is closed.",
        },
      ],
      review: {
        summary: "RANGE/ALLOW_FULL: 0 target allocations, 1 rebalance suggestions, target exposure 0.0%.",
        risk_notes: ["Purchase status is closed."],
      },
      agent_trace: [
        { name: "MarketDetectAgent", summary: "market ok" },
        { name: "FundFactorAgent", summary: "ranking done" },
        { name: "RiskAgent", summary: "blocked" },
        { name: "ReviewAgent", summary: "hold" },
      ],
    });

    expect(cycle.suggestions[0]).toMatchObject({
      symbol: "159915",
      amountLabel: "+200,000",
      blocked: true,
      reason: "Purchase status is closed.",
    });
    expect(cycle.agentChain.map((step) => step.name)).toEqual([
      "MarketDetectAgent",
      "FundFactorAgent",
      "RiskAgent",
      "ReviewAgent",
    ]);
    expect(summarizeDecision(cycle).headline).toContain("今日");
  });

  it("keeps feature ranking rows in fund order", () => {
    const payload = normalizeFundFeaturesPayload({
      as_of: "2026-06-03",
      items: [
        { fund_code: "159915", fund_name: "创业板ETF", return_20d: 0.12, category: "equity" },
        { fund_code: "000001", fund_name: "华夏成长混合", return_20d: 0.09, category: "equity" },
      ],
    });

    expect(payload.items[0].fundCode).toBe("159915");
    expect(payload.items[1].fundName).toBe("华夏成长混合");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- --runInBand
```

Expected: FAIL because Vitest is not configured and `fundDashboard` does not exist.

- [ ] **Step 3: Add the minimal test harness and normalization code**

`services/ashare-qlib-agent/frontend/package.json`

```json
{
  "scripts": {
    "dev": "vite --host 127.0.0.1 --port 5173",
    "build": "vite build",
    "preview": "vite preview --host 127.0.0.1 --port 5173",
    "test": "vitest"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "jsdom": "^25.0.1",
    "vitest": "^2.1.8"
  }
}
```

`services/ashare-qlib-agent/frontend/vitest.config.js`

```js
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
  },
});
```

`services/ashare-qlib-agent/frontend/src/test/setup.js`

```js
import "@testing-library/jest-dom";
```

`services/ashare-qlib-agent/frontend/src/lib/fundDashboard.js`

```js
const KEY_AGENTS = ["MarketDetectAgent", "FundFactorAgent", "PortfolioAgent", "RiskAgent", "ReviewAgent"];

export function normalizeCyclePayload(payload = {}) {
  const suggestions = Array.isArray(payload.suggestions) ? payload.suggestions : [];
  const trace = Array.isArray(payload.agent_trace) ? payload.agent_trace : [];
  return {
    cycleId: payload.cycle_id || "",
    market: payload.market || {},
    review: payload.review || {},
    suggestions: suggestions.map((item) => ({
      symbol: item.symbol || "",
      action: item.action || "HOLD",
      blocked: Boolean(item.blocked),
      reason: item.reason || "",
      deltaValue: Number(item.delta_value || 0),
      deltaWeight: Number(item.delta_weight || 0),
      targetWeight: Number(item.target_weight || 0),
      currentWeight: Number(item.current_weight || 0),
      amountLabel: formatSignedAmount(item.delta_value || 0),
      targetWeightLabel: formatPercent(item.target_weight || 0),
      currentWeightLabel: formatPercent(item.current_weight || 0),
      deltaWeightLabel: formatSignedPercent(item.delta_weight || 0),
    })),
    agentChain: trace.filter((step) => KEY_AGENTS.includes(step.name)).map((step) => ({
      name: step.name,
      summary: step.summary || "",
      status: step.status || "info",
    })),
    raw: payload,
  };
}

export function normalizeFundFeaturesPayload(payload = {}) {
  return {
    asOf: payload.as_of || "",
    items: (payload.items || []).map((item) => ({
      fundCode: item.fund_code || "",
      fundName: item.fund_name || "",
      category: item.category || "",
      return20d: Number(item.return_20d || 0),
    })),
  };
}

export function summarizeDecision(cycle) {
  const actionable = cycle.suggestions.filter((item) => !item.blocked);
  if (!cycle.suggestions.length) {
    return { headline: "今日建议：暂无调仓动作", tone: "neutral" };
  }
  if (!actionable.length) {
    return { headline: "今日建议：暂不执行调仓", tone: "warn" };
  }
  return { headline: `今日建议：执行 ${actionable.length} 项调整`, tone: "good" };
}

export function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

export function formatSignedPercent(value) {
  const amount = Number(value || 0) * 100;
  return `${amount >= 0 ? "+" : ""}${amount.toFixed(1)}%`;
}

export function formatSignedAmount(value) {
  const amount = Number(value || 0);
  return `${amount >= 0 ? "+" : ""}${Math.round(amount).toLocaleString("en-US")}`;
}
```

`services/ashare-qlib-agent/frontend/src/lib/api.js`

```js
const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8710";
const API_CANDIDATES = Array.from(new Set([DEFAULT_API_BASE, "http://127.0.0.1:8710"]));

export async function apiRequest(path, options = {}, activeApiBase, setActiveApiBase) {
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

export function getDefaultApiBase() {
  return DEFAULT_API_BASE;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- src/lib/fundDashboard.test.jsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/ashare-qlib-agent/frontend/package.json \
        services/ashare-qlib-agent/frontend/vitest.config.js \
        services/ashare-qlib-agent/frontend/src/test/setup.js \
        services/ashare-qlib-agent/frontend/src/lib/api.js \
        services/ashare-qlib-agent/frontend/src/lib/fundDashboard.js \
        services/ashare-qlib-agent/frontend/src/lib/fundDashboard.test.jsx
git commit -m "test: add fund dashboard data layer"
```

---

### Task 2: Replace The Shell And Navigation With Fund-First Workspace Layout

**Files:**
- Create: `services/ashare-qlib-agent/frontend/src/components/AppShell.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/AppShell.test.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/main.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/styles.css`
- Modify: `services/ashare-qlib-agent/frontend/index.html`

- [ ] **Step 1: Write the failing shell test**

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("shows fund-first navigation and refresh action", () => {
    const onNavigate = vi.fn();
    const onRefresh = vi.fn();

    render(
      <AppShell
        activePage="today"
        onNavigate={onNavigate}
        onRefresh={onRefresh}
        activeApiBase="http://127.0.0.1:8710"
        health={{ ok: true, service: "fund_rotation_agent", scheduler_enabled: true }}
        lastUpdated="2026-06-04 16:30:00"
        refreshing={false}
      >
        <div>content</div>
      </AppShell>
    );

    expect(screen.getByText("Fund Rotation Agent")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "今日建议" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "我的基金持仓" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "我的基金持仓" }));
    expect(onNavigate).toHaveBeenCalledWith("portfolio");

    fireEvent.click(screen.getByRole("button", { name: /刷新本日周期/i }));
    expect(onRefresh).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- src/components/AppShell.test.jsx
```

Expected: FAIL because `AppShell.jsx` does not exist.

- [ ] **Step 3: Write minimal shell implementation and wire it into `main.jsx`**

`services/ashare-qlib-agent/frontend/src/components/AppShell.jsx`

```jsx
import { Activity, Bot, RefreshCw, Wallet } from "lucide-react";

export function AppShell({
  activePage,
  onNavigate,
  onRefresh,
  activeApiBase,
  health,
  lastUpdated,
  refreshing,
  children,
}) {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Bot size={24} /></div>
          <div>
            <h1>Fund Rotation Agent</h1>
            <p>基金多智能体决策工作台</p>
          </div>
        </div>

        <nav className="page-nav" aria-label="主导航">
          <button className={`nav-tab ${activePage === "today" ? "active" : ""}`} onClick={() => onNavigate("today")}>
            今日建议
          </button>
          <button className={`nav-tab ${activePage === "portfolio" ? "active" : ""}`} onClick={() => onNavigate("portfolio")}>
            我的基金持仓
          </button>
        </nav>

        <div className="status-pill good">
          <Activity size={16} />
          <span>服务</span>
          <strong>{health?.ok ? "运行中" : "未连接"}</strong>
        </div>
        <div className="status-pill neutral">
          <Wallet size={16} />
          <span>调度</span>
          <strong>{health?.scheduler_enabled ? "已配置" : "未启用"}</strong>
        </div>

        <button className="refresh-button" type="button" onClick={onRefresh} disabled={refreshing}>
          <RefreshCw size={16} className={refreshing ? "spin" : ""} />
          刷新本日周期
        </button>

        <div className="sidebar-note"><span>API</span><code>{activeApiBase}</code></div>
        <div className="sidebar-note"><span>更新</span><strong>{lastUpdated || "-"}</strong></div>
      </aside>

      {children}
    </main>
  );
}
```

`services/ashare-qlib-agent/frontend/src/main.jsx`

```jsx
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AppShell } from "./components/AppShell";
import { apiRequest, getDefaultApiBase } from "./lib/api";
import "./styles.css";

function App() {
  const [activePage, setActivePage] = useState("today");
  const [health, setHealth] = useState(null);
  const [activeApiBase, setActiveApiBase] = useState(getDefaultApiBase());
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState("");

  async function loadHealth() {
    const payload = await apiRequest("/health", {}, activeApiBase, setActiveApiBase);
    setHealth(payload);
    setLastUpdated(new Date().toLocaleString("zh-CN", { hour12: false }));
  }

  useEffect(() => {
    loadHealth();
  }, []);

  return (
    <AppShell
      activePage={activePage}
      onNavigate={setActivePage}
      onRefresh={loadHealth}
      activeApiBase={activeApiBase}
      health={health}
      lastUpdated={lastUpdated}
      refreshing={refreshing}
    >
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">fund decision workbench</p>
            <h2>{activePage === "today" ? "今日建议" : "我的基金持仓"}</h2>
          </div>
        </header>
      </section>
    </AppShell>
  );
}

createRoot(document.getElementById("root")).render(<App />);
```

`services/ashare-qlib-agent/frontend/index.html`

```html
<title>Fund Rotation Agent</title>
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- src/components/AppShell.test.jsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/ashare-qlib-agent/frontend/src/components/AppShell.jsx \
        services/ashare-qlib-agent/frontend/src/components/AppShell.test.jsx \
        services/ashare-qlib-agent/frontend/src/main.jsx \
        services/ashare-qlib-agent/frontend/src/styles.css \
        services/ashare-qlib-agent/frontend/index.html
git commit -m "feat: add fund dashboard shell"
```

---

### Task 3: Implement Today Recommendation Page With Amount-First Suggestions

**Files:**
- Create: `services/ashare-qlib-agent/frontend/src/components/DecisionHero.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/AgentDecisionChain.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/RiskReviewPanel.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/FundRankingPanel.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.test.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/main.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/styles.css`

- [ ] **Step 1: Write the failing suggestion board test**

```jsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SuggestionBoard } from "./SuggestionBoard";

describe("SuggestionBoard", () => {
  it("renders amount-first cards and blocked state copy", () => {
    render(
      <SuggestionBoard
        suggestions={[
          {
            symbol: "159915",
            fundName: "创业板ETF",
            action: "INCREASE",
            amountLabel: "+200,000",
            currentWeightLabel: "0.0%",
            targetWeightLabel: "20.0%",
            deltaWeightLabel: "+20.0%",
            blocked: true,
            reason: "Purchase status is closed.",
          },
        ]}
      />
    );

    expect(screen.getByText("+200,000")).toBeInTheDocument();
    expect(screen.getByText("已阻断")).toBeInTheDocument();
    expect(screen.getByText("Purchase status is closed.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- src/components/SuggestionBoard.test.jsx
```

Expected: FAIL because `SuggestionBoard.jsx` does not exist.

- [ ] **Step 3: Write minimal Today Recommendation components**

`services/ashare-qlib-agent/frontend/src/components/DecisionHero.jsx`

```jsx
export function DecisionHero({ summary, market, totals }) {
  return (
    <section className="decision-hero">
      <div className="decision-hero__copy">
        <p className="eyebrow">today recommendation</p>
        <h2>{summary.headline}</h2>
        <p className="decision-hero__body">{summary.body}</p>
      </div>
      <div className="decision-hero__stats">
        <div className="metric-card"><span>建议动作数</span><strong>{totals.suggestionCount}</strong></div>
        <div className="metric-card"><span>建议金额</span><strong>{totals.totalDeltaAmount}</strong></div>
        <div className={`gate-card ${summary.tone}`}><span>{market.regime || "-"}</span><strong>{market.gate || "-"}</strong></div>
      </div>
    </section>
  );
}
```

`services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.jsx`

```jsx
export function SuggestionBoard({ suggestions }) {
  if (!suggestions.length) {
    return <div className="empty-state">今天没有新的基金调仓建议。</div>;
  }

  return (
    <section className="panel suggestion-board">
      <header><div><h3>建议列表</h3></div></header>
      <div className="suggestion-board__list">
        {suggestions.map((item) => (
          <article key={item.symbol} className={`suggestion-card ${item.blocked ? "blocked" : "active"}`}>
            <div className="suggestion-card__top">
              <div>
                <strong>{item.symbol}</strong>
                <p>{item.fundName || item.symbol}</p>
              </div>
              <span className={`suggestion-pill ${item.blocked ? "blocked" : "active"}`}>
                {item.blocked ? "已阻断" : "可执行"}
              </span>
            </div>
            <div className="suggestion-card__amount">{item.amountLabel}</div>
            <div className="suggestion-card__weights">
              <span>当前 {item.currentWeightLabel}</span>
              <span>目标 {item.targetWeightLabel}</span>
              <span>变化 {item.deltaWeightLabel}</span>
            </div>
            <p className="suggestion-card__reason">{item.reason}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
```

`services/ashare-qlib-agent/frontend/src/components/AgentDecisionChain.jsx`

```jsx
export function AgentDecisionChain({ steps }) {
  return (
    <section className="panel">
      <header><div><h3>多智能体裁决链</h3></div></header>
      <div className="agent-chain">
        {steps.map((step) => (
          <article key={step.name} className="agent-chain__item">
            <strong>{step.name}</strong>
            <p>{step.summary}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
```

`services/ashare-qlib-agent/frontend/src/components/RiskReviewPanel.jsx`

```jsx
export function RiskReviewPanel({ review }) {
  return (
    <section className="panel">
      <header><div><h3>风险审查</h3></div></header>
      <p className="review-text">{review.summary || "暂无复盘摘要"}</p>
      <div className="risk-list">
        {(review.riskNotes || []).map((note) => (
          <div key={note} className="risk-item"><span>{note}</span></div>
        ))}
      </div>
    </section>
  );
}
```

`services/ashare-qlib-agent/frontend/src/components/FundRankingPanel.jsx`

```jsx
export function FundRankingPanel({ items }) {
  return (
    <section className="panel">
      <header><div><h3>候选基金排名</h3></div></header>
      <div className="ranking-list">
        {items.map((item, index) => (
          <div key={item.fundCode} className="ranking-row">
            <strong>#{index + 1} {item.fundCode}</strong>
            <span>{item.fundName}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
```

`services/ashare-qlib-agent/frontend/src/main.jsx`

```jsx
import { DecisionHero } from "./components/DecisionHero";
import { SuggestionBoard } from "./components/SuggestionBoard";
import { AgentDecisionChain } from "./components/AgentDecisionChain";
import { RiskReviewPanel } from "./components/RiskReviewPanel";
import { FundRankingPanel } from "./components/FundRankingPanel";
import { normalizeCyclePayload, normalizeFundFeaturesPayload, summarizeDecision } from "./lib/fundDashboard";

// inside App
const [cycle, setCycle] = useState(null);
const [fundFeatures, setFundFeatures] = useState({ items: [] });

async function refreshCycle() {
  setRefreshing(true);
  try {
    await apiRequest("/scheduler/run-once", { method: "POST", body: JSON.stringify({ config_path: "" }) }, activeApiBase, setActiveApiBase);
    const latest = await apiRequest("/latest-cycle", {}, activeApiBase, setActiveApiBase);
    setCycle(normalizeCyclePayload(latest));
    const features = await apiRequest("/fund-features", {}, activeApiBase, setActiveApiBase);
    setFundFeatures(normalizeFundFeaturesPayload(features));
    await loadHealth();
  } finally {
    setRefreshing(false);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- src/components/SuggestionBoard.test.jsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/ashare-qlib-agent/frontend/src/components/DecisionHero.jsx \
        services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.jsx \
        services/ashare-qlib-agent/frontend/src/components/AgentDecisionChain.jsx \
        services/ashare-qlib-agent/frontend/src/components/RiskReviewPanel.jsx \
        services/ashare-qlib-agent/frontend/src/components/FundRankingPanel.jsx \
        services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.test.jsx \
        services/ashare-qlib-agent/frontend/src/main.jsx \
        services/ashare-qlib-agent/frontend/src/styles.css
git commit -m "feat: add today recommendation page"
```

---

### Task 4: Implement Portfolio Comparison And Full Agent Collaboration View

**Files:**
- Create: `services/ashare-qlib-agent/frontend/src/components/PortfolioCompareTable.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/AgentTimeline.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/main.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/styles.css`

- [ ] **Step 1: Write the failing portfolio view test**

```jsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PortfolioCompareTable } from "./PortfolioCompareTable";

describe("PortfolioCompareTable", () => {
  it("renders current vs target weights", () => {
    render(
      <PortfolioCompareTable
        rows={[
          {
            symbol: "159915",
            fundName: "创业板ETF",
            currentWeightLabel: "0.0%",
            targetWeightLabel: "20.0%",
            driftLabel: "+20.0%",
            action: "INCREASE",
          },
        ]}
      />
    );

    expect(screen.getByText("159915")).toBeInTheDocument();
    expect(screen.getByText("20.0%")).toBeInTheDocument();
    expect(screen.getByText("INCREASE")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- src/components/PortfolioCompareTable.test.jsx
```

Expected: FAIL because `PortfolioCompareTable.jsx` does not exist.

- [ ] **Step 3: Write minimal portfolio and timeline components**

`services/ashare-qlib-agent/frontend/src/components/PortfolioCompareTable.jsx`

```jsx
export function PortfolioCompareTable({ rows }) {
  if (!rows.length) {
    return <div className="empty-state">暂无基金持仓对比数据。</div>;
  }

  return (
    <section className="panel">
      <header><div><h3>我的基金持仓</h3></div></header>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>基金</th>
              <th>当前权重</th>
              <th>目标权重</th>
              <th>偏离</th>
              <th>建议动作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol}>
                <td>{row.symbol} {row.fundName}</td>
                <td>{row.currentWeightLabel}</td>
                <td>{row.targetWeightLabel}</td>
                <td>{row.driftLabel}</td>
                <td>{row.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

`services/ashare-qlib-agent/frontend/src/components/AgentTimeline.jsx`

```jsx
export function AgentTimeline({ trace, events, messages }) {
  const rows = [
    ...(trace || []).map((item) => ({ kind: "trace", title: item.name, body: item.summary || "" })),
    ...(events || []).map((item) => ({ kind: "event", title: item.agent || item.kind, body: item.summary || "" })),
    ...(messages || []).map((item) => ({ kind: "message", title: item.agent_name || "Agent", body: item.summary || "" })),
  ];

  if (!rows.length) {
    return <div className="empty-state">暂无完整协作记录。</div>;
  }

  return (
    <section className="panel">
      <header><div><h3>完整多智能体协作记录</h3></div></header>
      <div className="agent-timeline">
        {rows.map((row, index) => (
          <article key={`${row.kind}-${row.title}-${index}`} className="agent-timeline__item">
            <strong>{row.title}</strong>
            <p>{row.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
```

`services/ashare-qlib-agent/frontend/src/main.jsx`

```jsx
function buildPortfolioRows(cycle, holdings) {
  const bySymbol = new Map((cycle?.suggestions || []).map((item) => [item.symbol, item]));
  const holdingRows = (holdings?.holdings || []).map((row) => {
    const suggestion = bySymbol.get(row.symbol) || {};
    return {
      symbol: row.symbol,
      fundName: row.name || "",
      currentWeightLabel: `${(Number(row.weight || 0) * 100).toFixed(1)}%`,
      targetWeightLabel: `${(Number(suggestion.targetWeight || 0) * 100).toFixed(1)}%`,
      driftLabel: `${(((suggestion.targetWeight || 0) - Number(row.weight || 0)) * 100).toFixed(1)}%`,
      action: suggestion.action || "HOLD",
    };
  });
  return holdingRows;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- src/components/PortfolioCompareTable.test.jsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/ashare-qlib-agent/frontend/src/components/PortfolioCompareTable.jsx \
        services/ashare-qlib-agent/frontend/src/components/AgentTimeline.jsx \
        services/ashare-qlib-agent/frontend/src/main.jsx \
        services/ashare-qlib-agent/frontend/src/styles.css
git commit -m "feat: add fund portfolio and timeline views"
```

---

### Task 5: Remove Stock-Era Residue, Polish Styling, And Verify End-To-End

**Files:**
- Modify: `services/ashare-qlib-agent/frontend/src/main.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/styles.css`
- Modify: `services/ashare-qlib-agent/README.md`

- [ ] **Step 1: Write the failing build-level smoke expectation**

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm run build
```

Expected: FAIL or warnings due to stale stock-only imports, unused code, or missing new components during the transition.

- [ ] **Step 2: Remove stock-era assumptions and finalize copy**

`services/ashare-qlib-agent/frontend/src/main.jsx`

```jsx
// remove all references to:
// - /dashboard-data
// - /trades
// - stock orders
// - backtest/predictions/equity curve as primary homepage blocks
// - “我的持股”
// - “AShare Agent”
//
// ensure active pages are exactly:
// - "today"
// - "portfolio"
```

`services/ashare-qlib-agent/frontend/src/styles.css`

```css
/* add or adjust styles for:
   .decision-hero
   .decision-hero__stats
   .suggestion-board__list
   .suggestion-card
   .suggestion-pill
   .agent-chain
   .ranking-list
   .portfolio-grid
   .agent-timeline
   .empty-state
   while keeping the existing editorial palette and typography
*/
```

`services/ashare-qlib-agent/README.md`

```md
Frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend now targets:

- `GET /health`
- `GET /latest-cycle`
- `GET /fund-features`
- `GET/POST /holdings`
- `POST /scheduler/run-once`
```

- [ ] **Step 3: Run the full verification suite**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test
npm run build
```

Then run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m pytest tests -q
./.conda/bin/python -m mypy ashare_qlib_agent app
```

Expected:

- frontend tests PASS
- frontend build PASS
- backend pytest PASS
- backend mypy PASS

- [ ] **Step 4: Verify against running API**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
FUND_AGENT_CONFIG=config.postgres.yaml ./.conda/bin/uvicorn app.main:app --reload --port 8710
```

Then in another terminal:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
VITE_API_BASE=http://127.0.0.1:8710 npm run dev
```

Expected:

- Today Recommendation page loads with real `latest-cycle`
- manual refresh triggers `/scheduler/run-once`
- My Fund Portfolio page renders holdings vs target
- collaboration timeline renders `agent_trace`, `collaboration_events`, and `agent_messages`

- [ ] **Step 5: Commit**

```bash
git add services/ashare-qlib-agent/frontend/src/main.jsx \
        services/ashare-qlib-agent/frontend/src/styles.css \
        services/ashare-qlib-agent/README.md
git commit -m "feat: ship fund multi-agent dashboard"
```

---

## Self-Review

### Spec coverage

- decision-first homepage: covered by Task 3
- portfolio-vs-target second page: covered by Task 4
- preserve old workbench visual language: covered by Tasks 2 and 5
- map frontend to current fund endpoints: covered by Tasks 1, 3, and 5
- layered multi-agent visibility: covered by Tasks 3 and 4
- empty states and failure distinction: covered by Tasks 3 and 5

No spec gaps found.

### Placeholder scan

- Removed ambiguous frontend refresh branching from the plan and standardized on `POST /scheduler/run-once`.
- All tasks include exact files and commands.

### Type consistency

- Active pages are consistently `today` and `portfolio`.
- Primary normalized object is consistently `cycle`.
- Refresh action consistently targets `/scheduler/run-once`.
