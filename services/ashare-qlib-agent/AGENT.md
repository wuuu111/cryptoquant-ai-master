# AGENTS.md

## Project Goal

This project is an AI-powered fund allocation agent built with LangGraph-style multi-agent orchestration.

The original system was designed as a Qlib-based stock quant agent. The current direction is to transform it into a fund / ETF allocation agent because the project does not have access to professional real-time quant APIs.

The system should focus on daily fund decision-making, fund rotation, portfolio allocation, risk control, review, and strategy evolution.

## Core Product Direction

Build an AI Fund Rotation Agent.

The system should:
- Use fund NAV / ETF daily close data instead of stock-level OHLCV.
- Treat each fund or ETF as an instrument.
- Run on daily frequency.
- Generate allocation suggestions, not real trading orders.
- Support daily evaluation and weekly or event-driven rebalancing.
- Emphasize explainability, risk control, and multi-agent collaboration.

## Agent Design Principles

Do not make every agent call the LLM blindly.

Use this rule:

- Deterministic modules should remain rule-based and auditable.
- LLM modules should be used for explanation, critique, hypothesis generation, strategy review, and decision arbitration.

The LLM must not:
- Directly place orders.
- Bypass hard risk rules.
- Change portfolio weights without deterministic validation.
- Put untested new factors directly into live strategy.
- Invent data that is not present in the input.

## Target Agent Roles

Use the following agent roles:

- DataAgent: data engineer; loads fund NAV, ETF close, metadata, benchmark data.
- MarketDetectAgent: market regime analyst; detects growth, value, defensive, commodity, overseas, or risk-off regimes.
- MemoryAgent: historical experience retriever.
- ResearchModelAgent: model researcher; diagnoses fund scoring model stability.
- FundFactorAgent: fund factor researcher; computes fund scores.
- PortfolioAgent: portfolio manager; generates deterministic target allocation.
- RiskAgent: risk officer; checks hard and soft portfolio risk.
- CriticAgent: investment committee challenger.
- RebalanceCriticAgent or OrderCriticAgent: checks whether rebalancing is excessive or risky.
- SupervisorAgent: investment committee chair; makes final workflow decision.
- ExecutionAgent: generates subscription / redemption / ETF trade suggestions only.
- ManualConfirmationAgent: records human approval.
- ReviewAgent: post-market review analyst.
- EvolutionAgent: strategy research lead.
- MemoryWriteAgent: knowledge base manager.

## Data Scope

The first version should not depend on a professional quant API.

Use local CSV files first:

- data/fund_pool.csv
- data/fund_nav_daily.csv
- data/fund_metadata.csv
- data/benchmark_index.csv

Required fields can include:

fund_pool.csv:
- fund_code
- fund_name
- category
- fund_type
- tracking_index
- risk_level
- enabled

fund_nav_daily.csv:
- date
- fund_code
- nav
- daily_return

fund_metadata.csv:
- fund_code
- fund_name
- category
- fund_type
- fee
- aum
- manager
- purchase_status
- redemption_status

benchmark_index.csv:
- date
- index_code
- close
- daily_return

## Fund Factor Design

FundFactorAgent should calculate at least these factors:

1. MomentumScore
   - return_20d
   - return_60d
   - return_120d

2. RiskAdjustedReturnScore
   - return_60d / volatility_60d
   - return_120d / max_drawdown_120d

3. DrawdownControlScore
   - negative rank of max_drawdown_60d or max_drawdown_120d

4. TrendConfirmationScore
   - nav above 20-day moving average
   - 20-day moving average above 60-day moving average
   - nav close to 60-day high

5. RegimeMatchScore
   - fund category matches current market regime

6. OverheatPenalty
   - short-term return too high
   - volatility spike
   - drawdown expansion
   - theme crowding if available

Default score formula:

TotalScore =
0.30 * MomentumScore
+ 0.20 * RiskAdjustedReturnScore
+ 0.20 * TrendConfirmationScore
+ 0.15 * DrawdownControlScore
+ 0.15 * RegimeMatchScore
- 0.20 * OverheatPenalty

Weights can be adjusted by market regime, but the adjustment logic must be explicit and testable.

## Portfolio Rules

PortfolioAgent should generate fund allocation suggestions, not real orders.

Support three portfolio modes:

1. Conservative
   - Equity funds around 40%
   - Bond / short-duration bond funds around 40%
   - Gold / commodity around 10%
   - Cash / money market around 10%

2. Balanced
   - Equity funds around 60%
   - Bond / short-duration bond funds around 25%
   - Gold / commodity around 10%
   - Cash / money market around 5%

3. Aggressive
   - Equity funds around 80%
   - Bond / short-duration bond funds around 10%
   - Gold / commodity around 5%
   - Cash / money market around 5%

Hard constraints:
- Single fund max weight: 20%
- Single theme max weight: 30%
- High-volatility theme funds total max weight: 35%
- QDII max weight: 20%
- Gold / commodity max weight: 15%
- Minimum bond or cash allocation: 10%
- Single rebalance turnover should not exceed 30% unless risk reduction is triggered.

## RiskAgent Rules

RiskAgent must remain deterministic for hard risk checks.

Check:
- Equity allocation too high
- Single fund overweight
- Theme concentration
- Portfolio volatility
- Portfolio max drawdown
- Fund purchase / redemption status
- Excessive turnover
- Too much exposure to overheated themes
- Missing or stale NAV data

If hard risk fails, SupervisorAgent must not approve.

## SupervisorAgent Decisions

SupervisorAgent can output only:

- hold
- rebalance
- reduce_risk
- switch_style
- pause
- manual_review

Hard rules:
- If DataAgent reports data failure, do not approve rebalance.
- If RiskAgent hard risk check fails, do not approve rebalance.
- If RebalanceCriticAgent blocks, do not approve rebalance.
- If LLM output is invalid, fallback to rule-based decision.

## LLM Usage Rules

All LLM outputs must be structured JSON.

LLM can be used for:
- Market regime explanation.
- Fund score explanation.
- Risk summary.
- Rebalance critique.
- Supervisor decision explanation.
- Post-market review.
- Evolution suggestions.
- Memory summarization.

LLM cannot be used for:
- Directly changing raw data.
- Directly overriding hard risk checks.
- Directly placing orders.
- Directly approving untested strategies.
- Inventing fund performance or market data.

## Workflow

Daily workflow:

1. DataAgent loads fund and benchmark data.
2. MarketDetectAgent detects market regime.
3. MemoryAgent retrieves similar historical cases.
4. FundFactorAgent computes fund scores.
5. PortfolioAgent generates target allocation.
6. RiskAgent checks portfolio risk.
7. CriticAgent challenges the decision.
8. RebalanceCriticAgent checks whether the rebalance is necessary and safe.
9. SupervisorAgent makes final decision.
10. ExecutionAgent generates fund subscription / redemption / ETF trade suggestions.
11. ReviewAgent creates review.
12. EvolutionAgent proposes experiments.
13. MemoryWriteAgent stores validated lessons.

## Coding Rules

- Keep changes small and reviewable.
- Do not delete existing functionality unless explicitly requested.
- Prefer adding fund-specific modules instead of breaking the old stock-specific code immediately.
- Use clear type hints.
- Add fallback behavior for every LLM call.
- Add tests for scoring, risk rules, and supervisor hard constraints.
- Never commit API keys or credentials.
- Update README when behavior changes.