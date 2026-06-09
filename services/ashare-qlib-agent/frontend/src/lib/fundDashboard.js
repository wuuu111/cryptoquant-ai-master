const AGENT_LABELS = {
  MarketDetectAgent: "市场判断",
  FundMarketDetectAgent: "市场判断",
  FundFactorAgent: "基金评分",
  PortfolioAgent: "组合提案",
  FundPortfolioAgent: "组合提案",
  RiskAgent: "风险审查",
  FundRiskAgent: "风险审查",
  ExecutionAgent: "调仓生成",
  FundExecutionAgent: "调仓生成",
  ReviewAgent: "最终复核",
  FundReviewAgent: "最终复核",
  FundSupervisorAgent: "Supervisor 裁决",
};

const KEY_AGENTS = [
  "MarketDetectAgent",
  "FundMarketDetectAgent",
  "FundFactorAgent",
  "PortfolioAgent",
  "FundPortfolioAgent",
  "RiskAgent",
  "FundRiskAgent",
  "FundSupervisorAgent",
  "ReviewAgent",
  "FundReviewAgent",
];

export function normalizeHealthPayload(payload = {}) {
  return {
    ok: Boolean(payload.ok),
    service: payload.service || "fund_rotation_agent",
    databaseEnabled: Boolean(payload.database_enabled),
    schedulerEnabled: Boolean(payload.scheduler_enabled),
    database: payload.database || null,
  };
}

export function normalizeFundFeaturesPayload(payload = {}) {
  const items = Array.isArray(payload.items) ? payload.items : [];
  return {
    asOf: payload.as_of || "",
    count: Number(payload.count || items.length || 0),
    items: items.map((item, index) => ({
      rank: index + 1,
      fundCode: item.fund_code || "",
      fundName: item.fund_name || item.fund_code || "",
      category: item.category || "",
      fundType: item.fund_type || "",
      riskLevel: item.risk_level || "",
      nav: Number(item.nav || 0),
      dailyReturn: Number(item.daily_return || 0),
      return5d: Number(item.return_5d || 0),
      return20d: Number(item.return_20d || 0),
      return60d: Number(item.return_60d || 0),
      maxDrawdown60d: Number(item.max_drawdown_60d || 0),
      volatility60d: Number(item.volatility_60d || 0),
      purchaseStatus: item.purchase_status || "",
      redemptionStatus: item.redemption_status || "",
      stale: Boolean(item.stale),
      dataAsOf: item.data_as_of || "",
    })),
  };
}

export function normalizeAccountPayload(payload = {}) {
  return {
    accountId: payload.account_id || "default",
    baseCurrency: payload.base_currency || "CNY",
    targetTotalAssets: Number(payload.target_total_assets || 0),
    cashBalance: Number(payload.cash_balance || 0),
    positionsCount: Number(payload.positions_count || 0),
    pnl: {
      initialTotalAssets: Number(payload?.pnl?.initial_total_assets || 0),
      cashBalance: Number(payload?.pnl?.cash_balance || 0),
      marketValue: Number(payload?.pnl?.market_value || 0),
      currentTotalAssets: Number(payload?.pnl?.current_total_assets || 0),
      realizedPnl: Number(payload?.pnl?.realized_pnl || 0),
      unrealizedPnl: Number(payload?.pnl?.unrealized_pnl || 0),
      totalReturn: Number(payload?.pnl?.total_return || 0),
      totalReturnRate: Number(payload?.pnl?.total_return_rate || 0),
    },
  };
}

export function normalizePositionsPayload(payload = {}, accountPayload = null) {
  const items = Array.isArray(payload.items) ? payload.items : [];
  const totalAssets = Number(accountPayload?.targetTotalAssets || accountPayload?.pnl?.currentTotalAssets || 0);
  return {
    accountId: payload.account_id || "default",
    updatedAt: payload.updated_at || "",
    items: items.map((item) => ({
      symbol: item.symbol || "",
      fundName: item.fund_name || item.symbol || "",
      units: Number(item.units || 0),
      avgCost: Number(item.avg_cost || 0),
      lastNav: Number(item.last_nav || 0),
      marketValue: Number(item.market_value || 0),
      costValue: Number(item.cost_value || 0),
      weight: Number(item.weight || (totalAssets > 0 ? Number(item.market_value || 0) / totalAssets : 0)),
      unrealizedPnl: Number(item.unrealized_pnl || 0),
      unrealizedPnlRate: Number(item.unrealized_pnl_rate || 0),
    })),
  };
}

export function normalizeTradesPayload(payload = {}) {
  const items = Array.isArray(payload.items) ? payload.items : [];
  return {
    accountId: payload.account_id || "default",
    count: Number(payload.count || items.length),
    items: items.map((item) => ({
      tradeId: item.trade_id || "",
      symbol: item.symbol || "",
      fundName: item.fund_name || item.symbol || "",
      side: item.side || "BUY",
      amount: Number(item.amount || 0),
      units: Number(item.units || 0),
      price: Number(item.price || 0),
      source: item.source || "manual",
      suggestionId: item.suggestion_id || "",
      note: item.note || "",
      tradeTime: item.trade_time || "",
    })),
  };
}

export function buildFundLookup(featurePayload, positionsPayload) {
  const lookup = {};
  for (const item of featurePayload?.items || []) {
    lookup[item.fundCode] = {
      fundName: item.fundName,
      category: item.category,
      fundType: item.fundType,
      riskLevel: item.riskLevel,
    };
  }
  for (const item of positionsPayload?.items || []) {
    lookup[item.symbol] = {
      ...(lookup[item.symbol] || {}),
      fundName: item.fundName && item.fundName !== item.symbol
        ? item.fundName
        : lookup[item.symbol]?.fundName || item.fundName,
    };
  }
  return lookup;
}

export function normalizeCyclePayload(payload = {}, fundLookup = {}) {
  const suggestions = Array.isArray(payload.suggestions) ? payload.suggestions : [];
  const trace = Array.isArray(payload.agent_trace) ? payload.agent_trace : [];
  const events = Array.isArray(payload.collaboration_events) ? payload.collaboration_events : [];
  const targets = Array.isArray(payload.targets) ? payload.targets : [];
  const review = payload.review || {};
  const market = payload.market || {};

  const normalizedSuggestions = suggestions.map((item) => {
    const meta = fundLookup[item.symbol] || {};
    return {
      symbol: item.symbol || "",
      suggestionId: item.suggestion_id || "",
      fundName: meta.fundName || item.symbol || "",
      category: meta.category || "",
      action: item.action || "HOLD",
      actionLabel: localizeAction(item.action || "HOLD"),
      blocked: Boolean(item.blocked),
      reason: item.reason || "",
      deltaValue: Number(item.delta_value || 0),
      deltaWeight: Number(item.delta_weight || 0),
      targetWeight: Number(item.target_weight || 0),
      currentWeight: Number(item.current_weight || 0),
      applied: Boolean(item.applied),
      appliedTradeId: item.applied_trade_id || "",
      amountLabel: formatSignedAmount(item.delta_value || 0),
      targetWeightLabel: formatPercent(item.target_weight || 0),
      currentWeightLabel: formatPercent(item.current_weight || 0),
      deltaWeightLabel: formatSignedPercent(item.delta_weight || 0),
      tone: suggestionTone(item.action || "HOLD", Boolean(item.blocked)),
    };
  });

  const normalizedTargets = targets.map((item) => {
    const meta = fundLookup[item.symbol] || {};
    return {
      symbol: item.symbol || "",
      fundName: meta.fundName || item.symbol || "",
      targetWeight: Number(item.target_weight || 0),
      targetValue: Number(item.target_value || 0),
      reason: item.reason || "",
    };
  });

  return {
    cycleId: payload.cycle_id || "",
    workflow: payload.workflow || "",
    asOf: payload.as_of || "",
    market: {
      regime: market.regime || "",
      gate: market.gate || "",
      score: Number(market.score || 0),
      reason: market.reason || "",
      exposureMultiplier: Number(market.exposure_multiplier || 0),
    },
    review: {
      summary: review.summary || "",
      riskNotes: Array.isArray(review.risk_notes) ? review.risk_notes : [],
      metrics: review.metrics || {},
    },
    suggestions: normalizedSuggestions,
    targets: normalizedTargets,
    agentChain: trace
      .filter((step) => KEY_AGENTS.includes(step.name) || step.name === "FundSupervisorAgent")
      .map((step) => ({
        name: step.name,
        label: AGENT_LABELS[step.name] || step.name,
        summary: step.summary || "",
        role: step.role || "",
        status: step.status || "info",
        metrics: step.metrics || {},
      })),
    trace: trace.map((step) => ({
      name: step.name,
      label: AGENT_LABELS[step.name] || step.name,
      role: step.role || "",
      summary: step.summary || "",
      framework: step.framework || "",
      tools: Array.isArray(step.tools) ? step.tools : [],
      metrics: step.metrics || {},
      status: step.status || "info",
    })),
    events: events.map((event) => ({
      agent: event.agent || "",
      label: AGENT_LABELS[event.agent] || event.agent || "",
      kind: event.kind || "",
      summary: event.summary || "",
      severity: event.severity || "info",
      payload: event.payload || {},
    })),
    agentMessages: Array.isArray(payload.agent_messages) ? payload.agent_messages : [],
    blackboard: payload.blackboard || {},
    raw: payload,
  };
}

export function summarizeDecision(cycle) {
  const actionable = cycle.suggestions.filter((item) => !item.blocked && Math.abs(item.deltaValue) > 0);
  const blocked = cycle.suggestions.filter((item) => item.blocked);
  const totalDeltaValue = actionable.reduce((sum, item) => sum + Math.abs(item.deltaValue), 0);

  if (!cycle.cycleId) {
    return {
      headline: "今日建议：等待首轮基金周期",
      detail: "先执行一次同步与周期刷新，系统才会产生今日判断。",
      tone: "neutral",
      totalDeltaValue,
      totalDeltaValueLabel: formatCurrency(totalDeltaValue),
      actionableCount: 0,
      blockedCount: 0,
    };
  }

  if (!cycle.suggestions.length) {
    return {
      headline: "今日建议：暂无调仓动作",
      detail: "当前周期没有生成新的基金调仓建议。",
      tone: "neutral",
      totalDeltaValue,
      totalDeltaValueLabel: formatCurrency(totalDeltaValue),
      actionableCount: 0,
      blockedCount: 0,
    };
  }

  if (!actionable.length) {
    return {
      headline: "今日建议：先观察，不执行调仓",
      detail: blocked.length ? `本轮 ${blocked.length} 条建议被风险或申赎约束阻断。` : "当前没有可执行动作。",
      tone: "warn",
      totalDeltaValue,
      totalDeltaValueLabel: formatCurrency(totalDeltaValue),
      actionableCount: 0,
      blockedCount: blocked.length,
    };
  }

  return {
    headline: `今日建议：执行 ${actionable.length} 项基金调整`,
    detail: `建议变动总额 ${formatCurrency(totalDeltaValue)}，执行门控为 ${cycle.market.gate || "UNKNOWN"}。`,
    tone: "good",
    totalDeltaValue,
    totalDeltaValueLabel: formatCurrency(totalDeltaValue),
    actionableCount: actionable.length,
    blockedCount: blocked.length,
  };
}

export function buildDecisionReview(cycle) {
  const blackboard = cycle.blackboard || {};
  const portfolioReport = blackboard.portfolio_report || {};
  const supervisorReport = blackboard.supervisor_decision || {};
  const criticEvents = (cycle.events || []).filter((item) => item.agent === "CriticAgent" || item.label === "CriticAgent");
  const blockerEvents = criticEvents.filter((item) => item.severity === "blocker");
  const warningEvents = criticEvents.filter((item) => item.severity === "warning");
  const supervisorEvent = (cycle.events || []).find((item) => item.agent === "FundSupervisorAgent");
  const targetExposure = Number(
    cycle.targets?.reduce((sum, item) => sum + Number(item.targetWeight || 0), 0)
      || Object.values(portfolioReport.category_weights || {}).reduce((sum, value) => sum + Number(value || 0), 0),
  );
  const topFunds = (cycle.targets || []).slice(0, 4).map((item) => item.fundName || item.symbol).filter(Boolean);
  const actionableCount = (cycle.suggestions || []).filter((item) => !item.blocked).length;
  const blockedCount = (cycle.suggestions || []).filter((item) => item.blocked).length;
  const disputes = criticEvents.length
    ? criticEvents.map((item, index) => ({
      id: `${item.kind}-${index}`,
      title: inferDisputeTitle(item),
      proposal: describeProposalForDispute(item, {
        topFunds,
        targetCount: cycle.targets?.length || 0,
        targetExposure,
      }),
      critic: describeCriticEvent(item),
      outcome: describeSupervisorOutcome(supervisorReport, supervisorEvent),
      severity: item.severity || "info",
    }))
    : [{
      id: "none",
      title: "执行前一致",
      proposal: `组合提案共 ${cycle.targets?.length || 0} 个目标，总暴露 ${formatPercent(targetExposure)}。`,
      critic: "Critic 没有提出新的 blocker 或 warning。",
      outcome: describeSupervisorOutcome(supervisorReport, supervisorEvent),
      severity: "info",
    }];

  return {
    proposal: {
      targetCount: cycle.targets?.length || 0,
      targetExposure,
      targetExposureLabel: formatPercent(targetExposure),
      topFunds,
      categoryWeights: Object.entries(portfolioReport.category_weights || {})
        .map(([name, value]) => ({ name, weight: Number(value || 0), label: formatPercent(value || 0) }))
        .sort((left, right) => right.weight - left.weight),
    },
    critic: {
      blockerCount: blockerEvents.length,
      warningCount: warningEvents.length,
      objections: criticEvents.map((item) => ({
        summary: item.summary,
        severity: item.severity || "info",
      })),
    },
    supervisor: {
      decision: supervisorReport.decision || "",
      decisionLabel: localizeSupervisorDecision(supervisorReport.decision || ""),
      route: supervisorEvent?.payload?.route || (supervisorReport.decision === "approve" ? "execute" : "review"),
      routeLabel: localizeSupervisorRoute(supervisorEvent?.payload?.route || (supervisorReport.decision === "approve" ? "execute" : "review")),
      requiresHumanReview: Boolean(supervisorReport.requires_human_review),
      confidence: Number(supervisorReport.confidence || 0),
      reasoningSummary: supervisorReport.reasoning_summary || "等待 Supervisor 裁决。",
      supportingEvidence: Array.isArray(supervisorReport.supporting_evidence) ? supervisorReport.supporting_evidence : [],
      opposingEvidence: Array.isArray(supervisorReport.opposing_evidence) ? supervisorReport.opposing_evidence : [],
      requiredModifications: Array.isArray(supervisorReport.required_modifications) ? supervisorReport.required_modifications : [],
    },
    final: {
      actionableCount,
      blockedCount,
      summary: cycle.review?.summary || "",
      riskNotes: cycle.review?.riskNotes || [],
    },
    disputes,
  };
}

export function buildPortfolioRows(cycle, positionsPayload, featurePayload) {
  const lookup = buildFundLookup(featurePayload, positionsPayload);
  const currentBySymbol = Object.fromEntries((positionsPayload.items || []).map((item) => [item.symbol, item]));
  const targetBySymbol = Object.fromEntries((cycle.targets || []).map((item) => [item.symbol, item]));
  const suggestionBySymbol = Object.fromEntries((cycle.suggestions || []).map((item) => [item.symbol, item]));
  const symbols = Array.from(
    new Set([
      ...Object.keys(currentBySymbol),
      ...Object.keys(targetBySymbol),
      ...Object.keys(suggestionBySymbol),
    ]),
  );

  return symbols
    .map((symbol) => {
      const current = currentBySymbol[symbol];
      const target = targetBySymbol[symbol];
      const suggestion = suggestionBySymbol[symbol];
      const meta = lookup[symbol] || {};
      const currentWeight = current?.weight || suggestion?.currentWeight || 0;
      const targetWeight = target?.targetWeight || suggestion?.targetWeight || 0;
      return {
        symbol,
        fundName: meta.fundName || current?.fundName || target?.fundName || symbol,
        category: meta.category || "",
        marketValue: current?.marketValue || 0,
        currentWeight,
        targetWeight,
        drift: targetWeight - currentWeight,
        action: suggestion?.actionLabel || "观察",
        amountLabel: suggestion?.amountLabel || "0",
        blocked: Boolean(suggestion?.blocked),
        reason: suggestion?.reason || target?.reason || "",
        units: current?.units || 0,
        avgCost: current?.avgCost || 0,
        lastNav: current?.lastNav || 0,
        unrealizedPnl: current?.unrealizedPnl || 0,
        unrealizedPnlRate: current?.unrealizedPnlRate || 0,
      };
    })
    .sort((left, right) => {
      const delta = Math.abs(right.drift) - Math.abs(left.drift);
      if (delta !== 0) {
        return delta;
      }
      return right.marketValue - left.marketValue;
    });
}

export function localizeAction(action) {
  switch (action) {
    case "INCREASE":
      return "增加";
    case "DECREASE":
      return "降低";
    case "EXIT":
      return "退出";
    case "ENTER":
      return "建仓";
    default:
      return "观察";
  }
}

export function suggestionTone(action, blocked) {
  if (blocked) {
    return "blocked";
  }
  if (action === "DECREASE" || action === "EXIT") {
    return "trim";
  }
  if (action === "INCREASE" || action === "ENTER") {
    return "build";
  }
  return "neutral";
}

export function gateTone(gate) {
  if (gate === "BLOCK_NEW_RISK") {
    return "risk";
  }
  if (gate === "ALLOW_REDUCED") {
    return "warn";
  }
  if (gate === "ALLOW_FULL") {
    return "good";
  }
  return "neutral";
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

export function formatCurrency(value) {
  return `¥${Math.round(Number(value || 0)).toLocaleString("zh-CN")}`;
}

export function formatNumber(value, digits = 2) {
  return Number(value || 0).toFixed(digits);
}

export function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function localizeSupervisorDecision(decision) {
  switch (decision) {
    case "approve":
      return "通过";
    case "reduce":
      return "降档执行";
    case "pause":
      return "暂停";
    case "reject":
      return "驳回";
    case "request_revision":
      return "退回复算";
    default:
      return "待裁决";
  }
}

function localizeSupervisorRoute(route) {
  switch (route) {
    case "execute":
      return "进入执行";
    case "review":
      return "进入复核";
    case "risk":
      return "退回风控";
    case "portfolio":
      return "退回组合";
    case "factor":
      return "退回评分";
    default:
      return "待路由";
  }
}

function inferDisputeTitle(event) {
  if (event?.payload?.symbols?.length) {
    return "单基金上限";
  }
  if (Object.prototype.hasOwnProperty.call(event?.payload || {}, "allowed_exposure")) {
    return "总暴露约束";
  }
  if (event.kind === "model_disagreement") {
    return "模型分歧";
  }
  return "执行前异议";
}

function describeProposalForDispute(event, proposal) {
  if (event?.payload?.symbols?.length) {
    const names = proposal.topFunds.length ? proposal.topFunds.join("、") : `目标基金 ${event.payload.symbols.join("、")}`;
    return `${names} 被纳入目标组合，计划总暴露 ${formatPercent(proposal.targetExposure)}。`;
  }
  if (Object.prototype.hasOwnProperty.call(event?.payload || {}, "allowed_exposure")) {
    return `组合提案总暴露 ${formatPercent(proposal.targetExposure)}，目标数 ${proposal.targetCount}。`;
  }
  return `组合提案共 ${proposal.targetCount} 个目标，总暴露 ${formatPercent(proposal.targetExposure)}。`;
}

function describeCriticEvent(event) {
  if (event?.payload?.symbols?.length) {
    return `${event.summary} 涉及 ${event.payload.symbols.join("、")}。`;
  }
  if (Object.prototype.hasOwnProperty.call(event?.payload || {}, "allowed_exposure")) {
    return `${event.summary} 允许暴露 ${formatPercent(event.payload.allowed_exposure || 0)}。`;
  }
  return event.summary || "Critic 未提供更多说明。";
}

function describeSupervisorOutcome(supervisorReport, supervisorEvent) {
  const route = localizeSupervisorRoute(supervisorEvent?.payload?.route || (supervisorReport.decision === "approve" ? "execute" : "review"));
  const decision = localizeSupervisorDecision(supervisorReport.decision || "");
  return `${route} · ${decision || "待裁决"}`;
}
