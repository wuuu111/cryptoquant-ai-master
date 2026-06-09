from __future__ import annotations

import time
from collections import Counter, defaultdict
from typing import Any

from .fund_execution_agent import FundExecutionAgent
from .fund_factor_agent import FundFactorAgent
from .fund_portfolio_agent import FundPortfolioAgent
from .fund_risk_agent import FundRiskAgent
from .schemas import (
    AgentStep,
    CollaborationEvent,
    CycleResult,
    EvolutionExperiment,
    FactorScore,
    InstrumentFeature,
    MarketRegimeResult,
    PortfolioState,
    RebalanceSuggestion,
    ReviewReport,
    Signal,
    TargetPosition,
    to_jsonable,
)


class FundRotationAgent:
    def __init__(self, portfolio_mode: str = "balanced"):
        self.portfolio_mode = portfolio_mode
        self.factor = FundFactorAgent()
        self.portfolio = FundPortfolioAgent()
        self.risk = FundRiskAgent()
        self.execution = FundExecutionAgent()

    def run_cycle(self, snapshot, portfolio: PortfolioState) -> CycleResult:
        market = self._detect_market(snapshot)
        scores = self.factor.score(snapshot.instruments, market.regime)
        signals, targets = self.portfolio.build_targets(scores, market, portfolio, mode=self.portfolio_mode)
        signals, targets, blocked_suggestions, risk_reasons = self.risk.filter_targets(
            targets,
            signals,
            market,
            snapshot.instruments,
            portfolio,
        )
        suggestions = self.execution.build_suggestions(targets, portfolio, blocked_suggestions=blocked_suggestions)
        market_report = self._market_report(snapshot, market)
        factor_report = self._factor_report(scores)
        portfolio_report = self._portfolio_report(signals, targets, snapshot.instruments, portfolio)
        risk_report = self._risk_report(
            market,
            signals,
            targets,
            suggestions,
            blocked_suggestions,
            risk_reasons,
            snapshot.instruments,
            portfolio,
        )
        execution_report = self._execution_report(suggestions)
        review = self._build_review(market, targets, suggestions, risk_reasons)
        review_report = {
            "summary": review.summary,
            "risk_notes": review.risk_notes,
            "metrics": review.metrics,
        }
        blackboard = {
            "market_report": market_report,
            "factor_report": factor_report,
            "portfolio_report": portfolio_report,
            "risk_report": risk_report,
            "execution_report": execution_report,
            "review_report": review_report,
        }
        trace = self._agent_trace(market_report, factor_report, portfolio_report, risk_report, execution_report, review_report)
        events = self._collaboration_events(market_report, factor_report, portfolio_report, risk_report, execution_report, review_report)
        agent_messages = self._agent_messages(market_report, factor_report, portfolio_report, risk_report, execution_report, review_report)
        return CycleResult(
            cycle_id=f"fund_{int(time.time() * 1000)}",
            market=market,
            scores=scores,
            signals=signals,
            targets=targets,
            orders=[],
            suggestions=suggestions,
            review=review,
            evolution=[
                EvolutionExperiment(
                    name="fund_regime_tuning",
                    hypothesis="Adjust regime-match weights after observing more daily cycles.",
                    validation_plan="Collect 20+ daily fund cycles before reweighting regime-match logic.",
                )
            ],
            workflow="fund-legacy",
            agent_trace=trace,
            collaboration_events=events,
            agent_messages=agent_messages,
            blackboard=to_jsonable(blackboard),
        )

    def _detect_market(self, snapshot) -> MarketRegimeResult:
        benchmark_values = list(snapshot.benchmark_returns.values())
        benchmark_return = benchmark_values[0] if benchmark_values else 0.0
        if benchmark_return <= -0.02:
            return MarketRegimeResult("RISK_OFF", "BLOCK_NEW_RISK", benchmark_return, "Benchmark drawdown triggered risk off.", 0.0)
        if benchmark_return < 0:
            return MarketRegimeResult("BEAR_TREND", "ALLOW_REDUCED", benchmark_return, "Benchmark is mildly negative.", 0.60)
        if benchmark_return > 0.01:
            return MarketRegimeResult("BULL_TREND", "ALLOW_FULL", benchmark_return, "Benchmark trend is supportive.", 1.0)
        return MarketRegimeResult("RANGE", "ALLOW_FULL", benchmark_return, "Benchmark is range-bound.", 0.85)

    def _build_review(self, market, targets, suggestions, risk_reasons) -> ReviewReport:
        blocked = sum(1 for item in suggestions if item.blocked)
        target_exposure = sum(item.target_weight for item in targets)
        summary = (
            f"{market.regime}/{market.gate}: "
            f"{len(targets)} target allocations, {len(suggestions)} rebalance suggestions, "
            f"target exposure {target_exposure:.1%}."
        )
        return ReviewReport(
            summary=summary,
            risk_notes=risk_reasons,
            metrics={
                "targets": float(len(targets)),
                "suggestions": float(len(suggestions)),
                "blocked_suggestions": float(blocked),
                "target_exposure": target_exposure,
                "market_score": market.score,
            },
        )

    @staticmethod
    def _market_report(snapshot, market: MarketRegimeResult) -> dict[str, Any]:
        benchmark_code, benchmark_return = next(iter(snapshot.benchmark_returns.items()), ("BENCH", 0.0))
        return {
            "benchmark_code": benchmark_code,
            "benchmark_return": benchmark_return,
            "breadth": snapshot.breadth,
            "regime": market.regime,
            "gate": market.gate,
            "score": market.score,
            "exposure_multiplier": market.exposure_multiplier,
            "reason": market.reason,
            "agent_explanation": (
                f"基准 {benchmark_code} 当日收益 {benchmark_return:.2%}，"
                f"系统判断为 {market.regime}，执行门控为 {market.gate}。"
            ),
        }

    @staticmethod
    def _factor_report(scores: list[FactorScore]) -> dict[str, Any]:
        top = [
            {
                "symbol": item.symbol,
                "category": item.industry,
                "rank": item.rank,
                "combined_score": item.combined_score,
                "reason": item.reason,
                "diagnostics": item.diagnostics,
            }
            for item in scores[:5]
        ]
        bottom = [
            {
                "symbol": item.symbol,
                "category": item.industry,
                "rank": item.rank,
                "combined_score": item.combined_score,
                "reason": item.reason,
            }
            for item in scores[-3:]
        ]
        avg_score = sum(item.combined_score for item in scores) / len(scores) if scores else 0.0
        return {
            "ranked_count": len(scores),
            "average_score": avg_score,
            "top_funds": top,
            "weak_funds": bottom,
            "agent_explanation": "基金按动量、风险收益比、趋势确认、回撤控制、市场匹配和过热惩罚进行综合排序。",
        }

    @staticmethod
    def _portfolio_report(
        signals: list[Signal],
        targets: list[TargetPosition],
        instruments: list[InstrumentFeature],
        portfolio: PortfolioState,
    ) -> dict[str, Any]:
        by_symbol = {item.symbol: item for item in instruments}
        category_weights: dict[str, float] = defaultdict(float)
        target_rows = []
        for target in targets:
            instrument = by_symbol.get(target.symbol)
            category = instrument.category if instrument else "unknown"
            category_weights[category] += target.target_weight
            target_rows.append(
                {
                    "symbol": target.symbol,
                    "category": category,
                    "target_weight": target.target_weight,
                    "target_value": target.target_value,
                    "reason": target.reason,
                }
            )
        return {
            "portfolio_mode": "derived" if not signals else signals[0].reason.split(";")[0].replace("mode=", ""),
            "current_cash": portfolio.cash,
            "portfolio_equity": portfolio.equity,
            "signal_count": len(signals),
            "target_count": len(targets),
            "category_weights": dict(category_weights),
            "targets": target_rows,
            "agent_explanation": "先按组合模式分桶，再在每个类别内按分数挑选基金，并按市场门控缩放总敞口。",
        }

    @staticmethod
    def _risk_report(
        market: MarketRegimeResult,
        signals: list[Signal],
        targets: list[TargetPosition],
        suggestions: list[RebalanceSuggestion],
        blocked_suggestions: list[RebalanceSuggestion],
        reasons: list[str],
        instruments: list[InstrumentFeature],
        portfolio: PortfolioState,
    ) -> dict[str, Any]:
        by_symbol = {item.symbol: item for item in instruments}
        blocked_by_reason = Counter(item.reason for item in blocked_suggestions)
        category_weights: dict[str, float] = defaultdict(float)
        for target in targets:
            instrument = by_symbol.get(target.symbol)
            if instrument is not None:
                category_weights[instrument.category] += target.target_weight
        turnover = sum(abs(item.delta_weight) for item in suggestions if not item.blocked)
        return {
            "market_gate": market.gate,
            "passed": not reasons,
            "risk_notes": reasons,
            "blocked_count": len(blocked_suggestions),
            "blocked_by_reason": dict(blocked_by_reason),
            "post_risk_target_count": len(targets),
            "post_risk_signal_count": len(signals),
            "category_weights": dict(category_weights),
            "estimated_turnover": turnover,
            "portfolio_equity": portfolio.equity,
            "agent_explanation": "风险审查会阻断申购关闭、赎回关闭、NAV陈旧、商品/QDII超限及换手过高的方案。",
        }

    @staticmethod
    def _execution_report(suggestions: list[RebalanceSuggestion]) -> dict[str, Any]:
        action_counts = Counter(item.action for item in suggestions if not item.blocked)
        blocked = [item for item in suggestions if item.blocked]
        actionable = [
            {
                "symbol": item.symbol,
                "action": item.action,
                "delta_weight": item.delta_weight,
                "delta_value": item.delta_value,
                "reason": item.reason,
            }
            for item in suggestions
            if not item.blocked
        ]
        blocked_rows = [
            {
                "symbol": item.symbol,
                "action": item.action,
                "delta_weight": item.delta_weight,
                "delta_value": item.delta_value,
                "reason": item.reason,
            }
            for item in blocked
        ]
        return {
            "suggestion_count": len(suggestions),
            "action_counts": dict(action_counts),
            "blocked_count": len(blocked),
            "actionable_suggestions": actionable,
            "blocked_suggestions": blocked_rows,
            "agent_explanation": "执行层只输出申购、减仓、持有建议，不生成实际券商委托。",
        }

    def _agent_trace(
        self,
        market_report: dict[str, Any],
        factor_report: dict[str, Any],
        portfolio_report: dict[str, Any],
        risk_report: dict[str, Any],
        execution_report: dict[str, Any],
        review_report: dict[str, Any],
    ) -> list[AgentStep]:
        return [
            AgentStep(
                name="MarketDetectAgent",
                role="日频市场状态识别与门控",
                framework="fund-legacy",
                model="deterministic benchmark regime rules",
                tools=["benchmark_index.csv"],
                summary=market_report["agent_explanation"],
                metrics={
                    "benchmark_return": float(market_report["benchmark_return"]),
                    "exposure_multiplier": float(market_report["exposure_multiplier"]),
                },
                next_action="FundFactorAgent",
            ),
            AgentStep(
                name="FundFactorAgent",
                role="基金因子研究与排序解释",
                framework="fund-legacy",
                model="deterministic multi-factor scoring",
                tools=["fund_nav_daily.csv", "fund_metadata.csv"],
                summary=f"完成 {factor_report['ranked_count']} 只基金排序。",
                metrics={"ranked_count": float(factor_report["ranked_count"])},
                next_action="PortfolioAgent",
            ),
            AgentStep(
                name="PortfolioAgent",
                role="组合构建与目标权重提案",
                framework="fund-legacy",
                model="bucketed allocation policy",
                tools=["portfolio_mode", "target_caps"],
                summary=f"生成 {portfolio_report['target_count']} 个目标持仓。",
                metrics={"target_count": float(portfolio_report["target_count"])},
                next_action="RiskAgent",
            ),
            AgentStep(
                name="RiskAgent",
                role="硬规则风控审查",
                framework="fund-legacy",
                model="deterministic hard risk rules",
                tools=["purchase_status", "redemption_status", "stale_nav_check"],
                status="ok" if risk_report["passed"] else "warning",
                summary="风控通过。" if risk_report["passed"] else "风控发现需要阻断或提示的项。",
                metrics={
                    "blocked_count": float(risk_report["blocked_count"]),
                    "estimated_turnover": float(risk_report["estimated_turnover"]),
                },
                next_action="ExecutionAgent",
            ),
            AgentStep(
                name="ExecutionAgent",
                role="调仓建议生成",
                framework="fund-legacy",
                model="rebalance suggestion generator",
                tools=["target_weights", "current_portfolio"],
                summary=f"输出 {execution_report['suggestion_count']} 条调仓建议。",
                metrics={
                    "suggestion_count": float(execution_report["suggestion_count"]),
                    "blocked_count": float(execution_report["blocked_count"]),
                },
                next_action="ReviewAgent",
            ),
            AgentStep(
                name="ReviewAgent",
                role="审查总结",
                framework="fund-legacy",
                model="deterministic review summary",
                tools=["risk_report", "execution_report"],
                summary=str(review_report["summary"]),
                metrics={str(key): float(value) for key, value in dict(review_report["metrics"]).items()},
                next_action="end",
            ),
        ]

    @staticmethod
    def _collaboration_events(
        market_report: dict[str, Any],
        factor_report: dict[str, Any],
        portfolio_report: dict[str, Any],
        risk_report: dict[str, Any],
        execution_report: dict[str, Any],
        review_report: dict[str, Any],
    ) -> list[CollaborationEvent]:
        return [
            CollaborationEvent(
                agent="MarketDetectAgent",
                kind="claim",
                summary=market_report["agent_explanation"],
                payload={"gate": market_report["gate"], "regime": market_report["regime"]},
            ),
            CollaborationEvent(
                agent="FundFactorAgent",
                kind="proposal",
                summary=f"提出 {factor_report['ranked_count']} 只基金的日频排序结果。",
                payload={"top_funds": factor_report["top_funds"][:3]},
            ),
            CollaborationEvent(
                agent="PortfolioAgent",
                kind="proposal",
                summary=f"组合提案包含 {portfolio_report['target_count']} 个目标持仓。",
                payload={"category_weights": portfolio_report["category_weights"]},
            ),
            CollaborationEvent(
                agent="RiskAgent",
                kind="review_summary",
                summary="风险审查通过。" if risk_report["passed"] else "风险审查触发阻断或提示。",
                severity="info" if risk_report["passed"] else "warning",
                payload={"risk_notes": risk_report["risk_notes"], "blocked_by_reason": risk_report["blocked_by_reason"]},
            ),
            CollaborationEvent(
                agent="ExecutionAgent",
                kind="claim",
                summary=f"生成 {execution_report['suggestion_count']} 条调仓建议。",
                payload={"action_counts": execution_report["action_counts"]},
            ),
            CollaborationEvent(
                agent="ReviewAgent",
                kind="review_summary",
                summary=str(review_report["summary"]),
                severity="warning" if review_report["risk_notes"] else "info",
                payload={"metrics": review_report["metrics"]},
            ),
        ]

    @staticmethod
    def _agent_messages(
        market_report: dict[str, Any],
        factor_report: dict[str, Any],
        portfolio_report: dict[str, Any],
        risk_report: dict[str, Any],
        execution_report: dict[str, Any],
        review_report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {"agent_name": "MarketDetectAgent", "summary": market_report["agent_explanation"], "output": market_report},
            {"agent_name": "FundFactorAgent", "summary": factor_report["agent_explanation"], "output": factor_report},
            {"agent_name": "PortfolioAgent", "summary": portfolio_report["agent_explanation"], "output": portfolio_report},
            {"agent_name": "RiskAgent", "summary": risk_report["agent_explanation"], "output": risk_report},
            {"agent_name": "ExecutionAgent", "summary": execution_report["agent_explanation"], "output": execution_report},
            {"agent_name": "ReviewAgent", "summary": str(review_report["summary"]), "output": review_report},
        ]
