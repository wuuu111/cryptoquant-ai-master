import { describe, expect, it } from "vitest";
import {
  buildDecisionReview,
  normalizeAccountPayload,
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

  it("maps account payload into pnl-friendly shape", () => {
    const account = normalizeAccountPayload({
      account_id: "default",
      target_total_assets: 1000000,
      cash_balance: 180000,
      pnl: {
        initial_total_assets: 1000000,
        current_total_assets: 1070000,
        realized_pnl: 22000,
        unrealized_pnl: 48000,
        total_return: 70000,
        total_return_rate: 0.07,
      },
    });

    expect(account.targetTotalAssets).toBe(1000000);
    expect(account.cashBalance).toBe(180000);
    expect(account.pnl.totalReturnRate).toBe(0.07);
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

  it("builds supervisor and critic dispute review", () => {
    const cycle = normalizeCyclePayload({
      cycle_id: "fund_2",
      targets: [
        { symbol: "000001", target_weight: 0.2, target_value: 100000, reason: "mode=balanced" },
      ],
      suggestions: [
        { symbol: "000001", action: "INCREASE", delta_value: 100000, blocked: false },
      ],
      review: {
        summary: "RANGE/ALLOW_FULL: 1 target allocations, 1 rebalance suggestions, target exposure 20.0%.",
        risk_notes: ["Need review."],
      },
      collaboration_events: [
        {
          agent: "CriticAgent",
          kind: "pre_execution_objection",
          severity: "blocker",
          summary: "One or more targets exceed max position weight.",
          payload: { symbols: ["000001"] },
        },
        {
          agent: "FundSupervisorAgent",
          kind: "review_summary",
          severity: "warning",
          summary: "Supervisor routed to review.",
          payload: { route: "review" },
        },
      ],
      blackboard: {
        portfolio_report: {
          category_weights: { equity: 0.2 },
        },
        supervisor_decision: {
          decision: "pause",
          confidence: 0.2,
          reasoning_summary: "Critic raised 1 blocker.",
          supporting_evidence: [],
          opposing_evidence: ["Critic raised 1 blocker."],
          required_modifications: ["Reduce target weight."],
          requires_human_review: true,
        },
      },
    }, { "000001": { fundName: "华夏成长混合", category: "equity" } });

    const review = buildDecisionReview(cycle);

    expect(review.critic.blockerCount).toBe(1);
    expect(review.supervisor.routeLabel).toBe("进入复核");
    expect(review.disputes[0].title).toBe("单基金上限");
  });
});
