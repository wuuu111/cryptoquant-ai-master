# Fund Native Graph Ledger Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fund-only personal workbench that uses a fund-native graph/LLM workflow for recommendations, a unified PostgreSQL ledger for account/positions/trades/PnL, and a frontend that supports one-click suggestion apply, manual trade entry, and收益查看.

**Architecture:** Replace the current split between `portfolio-file` and `manual_holdings.json` with a single PostgreSQL-backed account ledger. Keep deterministic hard guards and data quality checks, but move the main recommendation flow onto a fund-native adaptation of the existing `graph_agent.py + llm.py + collaboration.py` stack. Update the frontend to consume the unified account/ledger APIs and present the multi-agent process as a conversation workbench in the existing visual style.

**Tech Stack:** Python, FastAPI, SQLAlchemy, PostgreSQL, AkShare, existing OpenAI-compatible LLM client, React, Vite, Vitest, pytest, mypy

---

### Task 1: Create Unified Account Ledger Schema

**Files:**
- Create: `services/ashare-qlib-agent/ashare_qlib_agent/fund_ledger.py`
- Modify: `services/ashare-qlib-agent/ashare_qlib_agent/fund_store.py`
- Modify: `services/ashare-qlib-agent/ashare_qlib_agent/schemas.py`
- Test: `services/ashare-qlib-agent/tests/test_fund_ledger.py`

- [ ] **Step 1: Write the failing ledger tests**

```python
from ashare_qlib_agent.fund_ledger import (
    AccountBook,
    LedgerTrade,
    PositionSnapshot,
    apply_trade_to_account,
    rebuild_positions,
    summarize_account_pnl,
)


def test_buy_trade_reduces_cash_and_creates_position():
    account = AccountBook(
        account_id="default",
        base_currency="CNY",
        target_total_assets=1_000_000.0,
        cash_balance=1_000_000.0,
    )
    trade = LedgerTrade(
        trade_id="t1",
        account_id="default",
        symbol="000001",
        fund_name="华夏成长混合",
        side="BUY",
        amount=80_000.0,
        units=60_240.9639,
        price=1.3280,
        source="manual",
    )

    next_account = apply_trade_to_account(account, trade)
    positions = rebuild_positions([], [trade], nav_by_symbol={"000001": 1.3280})

    assert next_account.cash_balance == 920_000.0
    assert positions[0].symbol == "000001"
    assert round(positions[0].market_value, 2) == 80_000.0


def test_sell_trade_realizes_profit_and_increases_cash():
    buy = LedgerTrade(
        trade_id="buy1",
        account_id="default",
        symbol="000001",
        fund_name="华夏成长混合",
        side="BUY",
        amount=80_000.0,
        units=60_240.9639,
        price=1.3280,
        source="manual",
    )
    sell = LedgerTrade(
        trade_id="sell1",
        account_id="default",
        symbol="000001",
        fund_name="华夏成长混合",
        side="SELL",
        amount=90_000.0,
        units=60_240.9639,
        price=1.4940,
        source="manual",
    )

    positions = rebuild_positions([], [buy, sell], nav_by_symbol={"000001": 1.4940})
    pnl = summarize_account_pnl(
        initial_total_assets=1_000_000.0,
        cash_balance=1_010_000.0,
        positions=positions,
        trades=[buy, sell],
    )

    assert positions == []
    assert pnl["realized_pnl"] > 0
    assert pnl["current_total_assets"] == 1_010_000.0
```

- [ ] **Step 2: Run the ledger tests to verify they fail**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m pytest tests/test_fund_ledger.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `fund_ledger` symbols.

- [ ] **Step 3: Implement ledger dataclasses and pure functions**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AccountBook:
    account_id: str
    base_currency: str
    target_total_assets: float
    cash_balance: float


@dataclass(frozen=True)
class LedgerTrade:
    trade_id: str
    account_id: str
    symbol: str
    fund_name: str
    side: str
    amount: float
    units: float
    price: float
    source: str
    suggestion_id: str = ""


def apply_trade_to_account(account: AccountBook, trade: LedgerTrade) -> AccountBook:
    cash = account.cash_balance - trade.amount if trade.side == "BUY" else account.cash_balance + trade.amount
    return AccountBook(
        account_id=account.account_id,
        base_currency=account.base_currency,
        target_total_assets=account.target_total_assets,
        cash_balance=round(cash, 2),
    )
```

- [ ] **Step 4: Extend PostgreSQL schema in `fund_store.py`**

```python
Table(
    "fund_accounts",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("base_currency", String, nullable=False),
    Column("target_total_assets", Float, nullable=False),
    Column("cash_balance", Float, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

Table(
    "fund_trade_ledger",
    metadata,
    Column("trade_id", String, primary_key=True),
    Column("account_id", String, nullable=False, index=True),
    Column("symbol", String, nullable=False, index=True),
    Column("fund_name", String, nullable=False),
    Column("side", String, nullable=False),
    Column("amount", Float, nullable=False),
    Column("units", Float, nullable=False),
    Column("price", Float, nullable=False),
    Column("source", String, nullable=False),
    Column("suggestion_id", String, nullable=False, default=""),
    Column("note", Text, nullable=False, default=""),
    Column("trade_time", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
```

- [ ] **Step 5: Run the ledger tests to verify they pass**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m pytest tests/test_fund_ledger.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add \
  ashare_qlib_agent/fund_ledger.py \
  ashare_qlib_agent/fund_store.py \
  ashare_qlib_agent/schemas.py \
  tests/test_fund_ledger.py
git commit -m "feat: add unified fund ledger schema"
```

### Task 2: Expose Account, Position, Trade, and Suggestion Apply APIs

**Files:**
- Create: `services/ashare-qlib-agent/ashare_qlib_agent/fund_account_service.py`
- Modify: `services/ashare-qlib-agent/app/main.py`
- Modify: `services/ashare-qlib-agent/ashare_qlib_agent/http_server.py`
- Test: `services/ashare-qlib-agent/tests/test_fund_account_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
from fastapi.testclient import TestClient
from app.main import app


def test_account_endpoints_round_trip():
    client = TestClient(app)

    create = client.post("/account", json={
        "account_id": "default",
        "base_currency": "CNY",
        "target_total_assets": 1_000_000,
        "cash_balance": 1_000_000,
    })
    assert create.status_code == 200

    read_back = client.get("/account")
    assert read_back.status_code == 200
    assert read_back.json()["target_total_assets"] == 1_000_000


def test_apply_suggestion_creates_trade_and_changes_positions():
    client = TestClient(app)

    response = client.post("/suggestions/s1/apply", json={"executed_price": 1.3280})
    assert response.status_code == 200
    payload = response.json()
    assert payload["trade"]["source"] == "suggestion_apply"
    assert payload["account"]["cash_balance"] < payload["account"]["target_total_assets"]
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m pytest tests/test_fund_account_api.py -q
```

Expected: FAIL with 404s for `/account` and `/suggestions/{id}/apply`.

- [ ] **Step 3: Implement account service methods**

```python
class FundAccountService:
    def get_account(self) -> dict: ...
    def upsert_account(self, payload: dict) -> dict: ...
    def list_positions(self) -> dict: ...
    def list_trades(self, limit: int = 50) -> dict: ...
    def create_manual_trade(self, payload: dict) -> dict: ...
    def apply_suggestion(self, suggestion_id: str, executed_price: float | None) -> dict: ...
```

- [ ] **Step 4: Add FastAPI endpoints**

```python
@app.get("/account")
def get_account() -> dict:
    return _account_service().get_account()


@app.post("/account")
def save_account(payload: AccountPayload) -> dict:
    return _account_service().upsert_account(payload.model_dump())


@app.get("/positions")
def get_positions() -> dict:
    return _account_service().list_positions()


@app.get("/trades")
def get_trades(limit: int = 50) -> dict:
    return _account_service().list_trades(limit=limit)


@app.post("/trades")
def create_trade(payload: ManualTradePayload) -> dict:
    return _account_service().create_manual_trade(payload.model_dump())


@app.post("/suggestions/{suggestion_id}/apply")
def apply_suggestion(suggestion_id: str, payload: ApplySuggestionPayload) -> dict:
    return _account_service().apply_suggestion(suggestion_id, payload.executed_price)
```

- [ ] **Step 5: Run the API tests to verify they pass**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m pytest tests/test_fund_account_api.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add \
  ashare_qlib_agent/fund_account_service.py \
  app/main.py \
  ashare_qlib_agent/http_server.py \
  tests/test_fund_account_api.py
git commit -m "feat: add account and trade APIs"
```

### Task 3: Move Fund Recommendation Flow onto Graph + LLM

**Files:**
- Create: `services/ashare-qlib-agent/ashare_qlib_agent/fund_graph_agent.py`
- Modify: `services/ashare-qlib-agent/ashare_qlib_agent/llm.py`
- Modify: `services/ashare-qlib-agent/ashare_qlib_agent/fund_live_cycle.py`
- Modify: `services/ashare-qlib-agent/ashare_qlib_agent/collaboration.py`
- Test: `services/ashare-qlib-agent/tests/test_fund_graph_agent.py`

- [ ] **Step 1: Write the failing workflow tests**

```python
from ashare_qlib_agent.fund_graph_agent import FundGraphWorkflow
from ashare_qlib_agent.schemas import PortfolioState


def test_fund_graph_workflow_returns_agent_trace_and_supervisor_summary(sample_snapshot):
    workflow = FundGraphWorkflow()
    result = workflow.run_cycle(
        sample_snapshot,
        PortfolioState(cash=200_000.0, equity=1_000_000.0, positions=[]),
    )

    assert result.workflow == "fund-graph"
    assert any(step.name == "FundSupervisorAgent" for step in result.agent_trace)
    assert result.review.summary
    assert result.blackboard["supervisor_decision"]["route"] in {"execute", "review", "portfolio", "risk", "factor"}


def test_blocked_suggestion_survives_llm_review(sample_snapshot_with_closed_purchase):
    workflow = FundGraphWorkflow()
    result = workflow.run_cycle(
        sample_snapshot_with_closed_purchase,
        PortfolioState(cash=200_000.0, equity=1_000_000.0, positions=[]),
    )

    blocked = [item for item in result.suggestions if item.blocked]
    assert blocked
    assert any("closed" in item.reason.lower() for item in blocked)
```

- [ ] **Step 2: Run the workflow tests to verify they fail**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m pytest tests/test_fund_graph_agent.py -q
```

Expected: FAIL with missing `FundGraphWorkflow`.

- [ ] **Step 3: Implement the fund-native graph wrapper**

```python
class FundGraphWorkflow:
    framework = "fund-graph"

    def run_cycle(self, snapshot: MarketSnapshot, portfolio: PortfolioState) -> CycleResult:
        # Reuse collaboration and llm client patterns from graph_agent.py
        # Use fund-specific market/factor/portfolio/risk/execution nodes
        ...
```

- [ ] **Step 4: Add fund-specific LLM methods without granting execution authority**

```python
def explain_fund_market_regime(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def explain_fund_factor_ranking(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def supervise_fund_decision(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def review_fund_cycle(self, payload: dict[str, Any]) -> dict[str, Any]: ...
```

- [ ] **Step 5: Switch `cycle_from_settings()` to use the graph workflow**

```python
agent = FundGraphWorkflow(
    portfolio_mode=settings.fund_data.portfolio_mode,
    llm_enabled=settings.fund_graph.llm_enabled,
)
result = agent.run_cycle(snapshot, portfolio_state)
```

- [ ] **Step 6: Run the workflow tests to verify they pass**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m pytest tests/test_fund_graph_agent.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add \
  ashare_qlib_agent/fund_graph_agent.py \
  ashare_qlib_agent/llm.py \
  ashare_qlib_agent/fund_live_cycle.py \
  ashare_qlib_agent/collaboration.py \
  tests/test_fund_graph_agent.py
git commit -m "feat: migrate fund workflow to graph and llm"
```

### Task 4: Replace Frontend Holdings with Unified Account + PnL Workbench

**Files:**
- Modify: `services/ashare-qlib-agent/frontend/src/lib/api.js`
- Modify: `services/ashare-qlib-agent/frontend/src/lib/fundDashboard.js`
- Modify: `services/ashare-qlib-agent/frontend/src/main.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/AccountOverview.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/TradeLedgerTable.jsx`
- Create: `services/ashare-qlib-agent/frontend/src/components/ManualTradeDrawer.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/components/AgentDecisionChain.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/styles.css`
- Test: `services/ashare-qlib-agent/frontend/src/lib/fundDashboard.test.jsx`

- [ ] **Step 1: Write the failing frontend normalization tests**

```jsx
import { describe, expect, it } from "vitest";
import { normalizeAccountPayload, normalizePositionsPayload } from "./fundDashboard";

describe("account normalization", () => {
  it("maps account and pnl fields for portfolio page", () => {
    const account = normalizeAccountPayload({
      target_total_assets: 1000000,
      cash_balance: 180000,
      pnl: { total_return: 70000, total_return_rate: 0.075 },
    });

    expect(account.targetTotalAssets).toBe(1000000);
    expect(account.cashBalance).toBe(180000);
    expect(account.pnl.totalReturnRate).toBe(0.075);
  });
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- --run
```

Expected: FAIL with missing `normalizeAccountPayload`.

- [ ] **Step 3: Add API clients for account/positions/trades/apply**

```js
export function fetchAccount(activeApiBase, setActiveApiBase) {
  return apiRequest("/account", {}, activeApiBase, setActiveApiBase);
}

export function fetchPositions(activeApiBase, setActiveApiBase) {
  return apiRequest("/positions", {}, activeApiBase, setActiveApiBase);
}

export function fetchTrades(activeApiBase, setActiveApiBase, limit = 50) {
  return apiRequest(`/trades?limit=${encodeURIComponent(limit)}`, {}, activeApiBase, setActiveApiBase);
}

export function applySuggestion(suggestionId, body, activeApiBase, setActiveApiBase) {
  return apiRequest(`/suggestions/${encodeURIComponent(suggestionId)}/apply`, {
    method: "POST",
    body: JSON.stringify(body),
  }, activeApiBase, setActiveApiBase);
}
```

- [ ] **Step 4: Replace portfolio page state with unified account and positions**

```jsx
const [account, setAccount] = useState(normalizeAccountPayload({}));
const [positions, setPositions] = useState(normalizePositionsPayload({}));
const [trades, setTrades] = useState(normalizeTradesPayload({}));
```

- [ ] **Step 5: Redesign multi-agent area as a dialogue workbench**

```jsx
<Panel title="多 Agent 协作对话台" icon={<BrainCircuit size={18} />}>
  <AgentTimeline
    variant="dialogue"
    trace={cycle.trace}
    events={cycle.events}
    messages={cycle.agentMessages}
    supervisor={cycle.supervisorDecision}
  />
</Panel>
```

- [ ] **Step 6: Run frontend tests and build**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- --run
npm run build
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add \
  frontend/src/lib/api.js \
  frontend/src/lib/fundDashboard.js \
  frontend/src/lib/fundDashboard.test.jsx \
  frontend/src/main.jsx \
  frontend/src/components/AccountOverview.jsx \
  frontend/src/components/TradeLedgerTable.jsx \
  frontend/src/components/ManualTradeDrawer.jsx \
  frontend/src/components/AgentDecisionChain.jsx \
  frontend/src/styles.css
git commit -m "feat: add unified fund account dashboard"
```

### Task 5: Add One-Click Apply and Manual Trade Recording UX

**Files:**
- Modify: `services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/main.jsx`
- Modify: `services/ashare-qlib-agent/frontend/src/lib/api.js`
- Test: `services/ashare-qlib-agent/frontend/src/components/SuggestionBoard.test.jsx`

- [ ] **Step 1: Write the failing interaction tests**

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { SuggestionBoard } from "./SuggestionBoard";

it("shows apply button for actionable suggestions", () => {
  render(<SuggestionBoard suggestions={[{
    suggestionId: "s1",
    symbol: "000001",
    action: "INCREASE",
    deltaValue: 80000,
    blocked: false,
  }]} onApply={() => {}} />);

  expect(screen.getByRole("button", { name: "一键调仓" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the interaction tests to verify they fail**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- --run SuggestionBoard.test.jsx
```

Expected: FAIL because `SuggestionBoard` has no apply button callback.

- [ ] **Step 3: Add apply and manual adjustment actions to suggestion cards**

```jsx
{!item.blocked ? (
  <button type="button" onClick={() => onApply(item)}>一键调仓</button>
) : (
  <button type="button" onClick={() => onInspect(item)}>查看协作理由</button>
)}
<button type="button" onClick={() => onManualAdjust(item)}>手动调整</button>
```

- [ ] **Step 4: Wire apply to backend and refresh account state**

```jsx
async function onApplySuggestion(item) {
  await applySuggestion(item.suggestionId, {}, activeApiBase, setActiveApiBase);
  await loadSnapshot({ preserveMessage: true });
  setActionMessage(`已将 ${item.symbol} 建议写入本地账本。`);
}
```

- [ ] **Step 5: Run the interaction tests and build**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm test -- --run
npm run build
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add \
  frontend/src/components/SuggestionBoard.jsx \
  frontend/src/components/SuggestionBoard.test.jsx \
  frontend/src/main.jsx \
  frontend/src/lib/api.js
git commit -m "feat: add apply suggestion and manual trade actions"
```

### Task 6: Update CLI, Scheduler, Docs, and End-to-End Verification

**Files:**
- Modify: `services/ashare-qlib-agent/ashare_qlib_agent/cli.py`
- Modify: `services/ashare-qlib-agent/ashare_qlib_agent/fund_scheduler.py`
- Modify: `services/ashare-qlib-agent/config.postgres.yaml`
- Modify: `services/ashare-qlib-agent/README.md`
- Create: `services/ashare-qlib-agent/tests/test_fund_end_to_end_account_flow.py`

- [ ] **Step 1: Write the failing end-to-end test**

```python
def test_scheduler_cycle_and_manual_trade_update_same_account(settings):
    scheduler = FundTaskScheduler(settings)
    first = scheduler.run_once()
    assert first.cycle["suggestions"]

    service = FundAccountService.from_settings(settings)
    trade = service.create_manual_trade({
        "symbol": "000001",
        "fund_name": "华夏成长混合",
        "side": "BUY",
        "amount": 10000,
        "price": 1.3280,
    })

    account = service.get_account()
    positions = service.list_positions()

    assert trade["trade"]["source"] == "manual"
    assert account["cash_balance"] < account["target_total_assets"]
    assert any(item["symbol"] == "000001" for item in positions["items"])
```

- [ ] **Step 2: Run the end-to-end test to verify it fails**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m pytest tests/test_fund_end_to_end_account_flow.py -q
```

Expected: FAIL because scheduler and account service do not share one ledger yet.

- [ ] **Step 3: Update CLI and scheduler to use the unified account**

```python
fund_cycle.add_argument("--account-id", default="default")
run_scheduler.add_argument("--account-id", default="default")
```

```python
portfolio = FundAccountService.from_settings(self.settings).to_portfolio_state(account_id="default")
cycle = cycle_from_settings(self.settings, portfolio=portfolio)
```

- [ ] **Step 4: Update docs and config**

```yaml
fund_graph:
  enabled: true
  llm_enabled: true

account:
  default_account_id: default
  base_currency: CNY
```

- [ ] **Step 5: Run full verification**

Run:

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m mypy ashare_qlib_agent app
./.conda/bin/python -m pytest tests -q
cd frontend
npm test -- --run
npm run build
```

Expected:

- `mypy`: `Success: no issues found`
- `pytest`: all pass
- `npm test`: pass
- `npm run build`: pass

- [ ] **Step 6: Commit**

```bash
git add \
  ashare_qlib_agent/cli.py \
  ashare_qlib_agent/fund_scheduler.py \
  config.postgres.yaml \
  README.md \
  tests/test_fund_end_to_end_account_flow.py
git commit -m "feat: document unified graph-ledger fund workflow"
```

## Plan Self-Review

- Spec coverage:
  - Fund-native graph workflow: Task 3
  - Unified ledger and total assets: Tasks 1, 2, 6
  - One-click apply and manual trade entry: Tasks 2 and 5
  -收益与交易流水: Tasks 1, 2, 4
  - Frontend old-style multi-agent dialogue workbench: Task 4
- Placeholder scan:
  - No `TODO`/`TBD` placeholders remain.
- Type consistency:
  - Unified naming uses `AccountBook`, `LedgerTrade`, `FundAccountService`, `FundGraphWorkflow`, and `suggestionId` consistently across tasks.
