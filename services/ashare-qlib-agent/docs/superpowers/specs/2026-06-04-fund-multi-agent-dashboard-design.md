# Fund Multi-Agent Dashboard Design

## Goal

Redesign the frontend from the old stock-oriented dashboard into a fund-first personal decision workbench while preserving the "multi-agent collaboration control room" feel.

The page should answer one question first:

- what should I do with my fund portfolio today

The multi-agent workflow remains visible, but as explanation and traceability rather than the first-screen focal point.

## User Intent

The target user is one person running a daily fund workflow.

Primary task:

- open the page once per day
- see whether a rebalance is recommended
- understand suggested amounts first
- inspect target weights and blocking reasons second

Secondary task:

- review how the agents arrived at the decision
- inspect current portfolio versus target portfolio

## Design Principles

- decision-first, not research-first
- preserve the existing workbench tone instead of replacing it with a generic SaaS dashboard
- keep the multi-agent identity visible
- default to concise actionable output, with deeper explanation on demand
- align the frontend strictly to current fund endpoints and current fund data structures

## Visual Direction

The redesign should inherit the strongest visual traits of the previous stock frontend:

- paper-toned background and editorial texture
- serif display headings
- mono utility labels and compact system status language
- panel-based information architecture
- trading-desk / control-room atmosphere

What changes:

- brand language changes from A-share/stock to fund rotation
- hero content changes from model/backtest emphasis to action recommendation emphasis
- old stock prediction and order widgets are removed
- holdings semantics change from stock trades to fund allocation and rebalance

## Information Architecture

### Page 1: Today Recommendation

This is the default page.

The first screen should contain:

- a decision hero with today's recommended action
- summary metrics for suggestion count, recommended total amount, and market/risk gate
- a short verdict card explaining whether the system is actionable or blocked

Below the hero:

- suggestion board
  - default emphasis: money amount
  - secondary detail: target weight, current weight, delta weight
  - tertiary detail: blocking reason / execution reason / agent explanation
- compact agent decision chain
  - market detect
  - factor ranking
  - portfolio construction
  - risk review
  - final review

Lower on the page:

- risk review summary
- quick candidate ranking preview
- entry point to the full collaboration timeline

### Page 2: My Fund Portfolio

This is the secondary page.

The top section should compare:

- current holdings
- current weights
- target weights
- drift
- suggested action

Supporting sections:

- candidate fund ranking
- complete multi-agent collaboration trace
- latest cycle review summary

## Component Architecture

The current large single-file React page should be split into focused components.

Proposed components:

- `AppShell`
- `SidebarStatus`
- `DecisionHero`
- `DecisionMetrics`
- `SuggestionBoard`
- `SuggestionCard`
- `AgentDecisionChain`
- `RiskReviewPanel`
- `FundRankingPanel`
- `PortfolioCompareTable`
- `AgentTimeline`
- `CycleSummaryPanel`

Shared utilities:

- API client with endpoint fallback
- shape normalizers for fund cycle payloads
- formatting helpers for currency, percent, fund labels, and gate labels

## Data Mapping

The old frontend assumes stock-era endpoints such as:

- `/dashboard-data`
- `/trades`
- stock predictions, backtest, orders, equity curve

The redesigned frontend should map to the current fund APIs:

- `GET /health`
- `GET /fund-features`
- `GET /latest-cycle`
- `POST /fund-cycle`
- `POST /sync-fund-data`
- `POST /scheduler/run-once`
- `GET /holdings`
- `POST /holdings`

Primary screen data source:

- `GET /latest-cycle`

Supporting data source:

- `GET /fund-features`

Manual refresh actions:

- `POST /scheduler/run-once` for a full new daily cycle

For the first implementation, the frontend should expose only one manual refresh action:

- `POST /scheduler/run-once`

`POST /fund-cycle` remains a backend capability, but it is not part of the first frontend interaction model.

## State Model

Frontend state should be simplified around the current workflow:

- `health`
- `latestCycle`
- `fundFeatures`
- `holdings`
- `activePage`
- `activeApiBase`
- `loading` / `error` / `actionMessage`

The old trade ledger editing state should be removed from the default UX. The current holdings page should be fund-position oriented, not stock-trade-entry oriented.

If manual holding editing remains, it should be modeled as:

- fund code
- fund name
- current market value
- current weight
- optional note

not buy/sell quantity rows.

## Multi-Agent Presentation Strategy

The multi-agent characteristic must remain visible, but in layers.

Layer 1:

- concise agent decision chain on the Today Recommendation page
- one conclusion line per key agent

Layer 2:

- full collaboration detail on the portfolio page
- render `agent_trace`, `collaboration_events`, and `agent_messages`

Layer 3:

- structured reasoning attached to each suggestion card
- show which agent or rule blocked or approved the move

This preserves the identity of the system as a collaborative agent workflow without sacrificing first-screen clarity.

## Error Handling

The redesign should explicitly handle:

- no `latest-cycle` yet
- PostgreSQL/DB unavailable
- AkShare sync not yet run
- cycle exists but all suggestions are blocked
- fund feature list unavailable
- partial payloads where some collaboration arrays are missing

UX behavior:

- show actionable empty states instead of generic "暂无数据"
- distinguish "system is healthy but action is blocked" from "system failed"
- expose the active API base and last refresh time

## Implementation Scope

### In Scope

- rewrite the frontend as a fund-first dashboard
- remove stock-specific widgets from the rendered UI
- preserve existing overall aesthetic direction
- connect to current fund endpoints
- keep multi-agent collaboration visible in a layered way

### Out of Scope

- redesigning backend payload contracts
- adding broker execution UX
- building a new chart-heavy research terminal
- implementing historical analytics beyond current cycle/history payloads

## Testing Plan

- ensure the page loads against the current FastAPI service on `8710`
- verify `latest-cycle` driven rendering with real PostgreSQL-backed payloads
- verify empty-state rendering when no cycle exists
- verify blocked suggestion rendering
- verify page navigation between Today Recommendation and My Fund Portfolio
- run frontend build after the refactor

## Recommended Implementation Order

1. replace stock-era API assumptions with fund API assumptions
2. restructure page navigation and shell
3. implement Today Recommendation page
4. implement My Fund Portfolio page
5. add full collaboration timeline and detailed suggestion explanations
6. polish styling to match the old workbench visual language

## Open Decision Log

Confirmed user preferences:

- the app is for daily personal use, not always-on monitoring
- the first screen should answer whether to rebalance today
- suggestion cards should show amount first and weight second
- homepage should show a compact agent chain, with full collaboration details deeper in the UI
- the second main page should be current portfolio versus target portfolio
- the visual language should reference the previous stock frontend instead of switching to an entirely new style
