from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .blackboard import append_agent_message
from .collaboration import AgentMemoryStore, CriticAgent, SupervisorAgent, SupervisorDecision
from .fund_agent import FundRotationAgent
from .llm import LLMClient
from .schemas import (
    AgentStep,
    CollaborationEvent,
    CycleResult,
    EvolutionExperiment,
    MarketSnapshot,
    PortfolioState,
    ReviewReport,
    to_jsonable,
)


class FundGraphWorkflow:
    framework = "fund-graph"

    def __init__(
        self,
        portfolio_mode: str = "balanced",
        *,
        llm: LLMClient | None = None,
        registry_dir: str | Path = "./registry",
        max_position_weight: float = 0.20,
    ):
        self.core = FundRotationAgent(portfolio_mode=portfolio_mode)
        self.portfolio_mode = portfolio_mode
        self.memory = AgentMemoryStore(registry_dir)
        self.critic = CriticAgent(max_position_weight=max_position_weight)
        self.supervisor = SupervisorAgent()
        self.llm = llm or LLMClient.from_env()

    def run_cycle(self, snapshot: MarketSnapshot, portfolio: PortfolioState) -> CycleResult:
        cycle_id = f"fund_{int(time.time() * 1000)}"
        market = self.core._detect_market(snapshot)
        market_report = self.core._market_report(snapshot, market)
        memory_context = self.memory.recent(limit=5)
        if memory_context:
            memory_summary = self.llm.retrieve_memory_context(
                {
                    "market_regime_report": market_report,
                    "recent_memory": memory_context,
                    "recent_review_report": {},
                    "recent_evolution_plan": {},
                    "recent_factor_performance": {},
                }
            )
        else:
            memory_summary = {
                "similar_cases": [],
                "recent_failures": [],
                "risk_reminders": [],
                "confidence": 0.2,
                "warnings": ["No sufficient historical memory found."],
            }

        llm_market = self.llm.explain_fund_market_regime(market_report)
        if llm_market.get("regime_commentary"):
            market_report["llm_commentary"] = llm_market["regime_commentary"]

        scores = self.core.factor.score(snapshot.instruments, market.regime)
        factor_report = self.core._factor_report(scores)
        llm_factor = self.llm.explain_fund_factor_ranking(
            {
                "market": to_jsonable(market),
                "scores": to_jsonable(scores[:10]),
                "factor_report": factor_report,
            }
        )
        if llm_factor.get("ranking_summary"):
            factor_report["llm_summary"] = llm_factor["ranking_summary"]

        signals, targets = self.core.portfolio.build_targets(scores, market, portfolio, mode=self.portfolio_mode)
        portfolio_report = self.core._portfolio_report(signals, targets, snapshot.instruments, portfolio)

        signals, targets, blocked_suggestions, risk_reasons = self.core.risk.filter_targets(
            targets,
            signals,
            market,
            snapshot.instruments,
            portfolio,
        )
        suggestions = self.core.execution.build_suggestions(targets, portfolio, blocked_suggestions=blocked_suggestions)
        risk_report = self.core._risk_report(
            market,
            signals,
            targets,
            suggestions,
            blocked_suggestions,
            risk_reasons,
            snapshot.instruments,
            portfolio,
        )
        execution_report = self.core._execution_report(suggestions)

        critic_events = self.critic.critique_pre_execution(
            market=market,
            targets=targets,
            signals=signals,
            market_advice={"available": False, "risk_off_probability": 0.0},
        )
        llm_decision = self.llm.supervise_fund_decision(
            {
                "market_report": market_report,
                "factor_report": factor_report,
                "portfolio_report": portfolio_report,
                "risk_report": {
                    "hard_risk_check": {
                        "passed": risk_report["passed"],
                        "blocking_reasons": risk_report["risk_notes"],
                    }
                },
                "critic_events": [to_jsonable(item) for item in critic_events],
                "memory_context": memory_summary,
            }
        )
        supervisor_report = self.supervisor.apply_guardrails(
            {
                "llm_decision": llm_decision,
                "hard_risk_passed": risk_report["passed"],
                "risk_report": {
                    "hard_risk_check": {
                        "passed": risk_report["passed"],
                        "blocking_reasons": risk_report["risk_notes"],
                    }
                },
                "critic_report": {
                    "blockers": sum(1 for item in critic_events if item.severity == "blocker"),
                },
                "data_quality_report": {"data_passed": True},
            }
        )
        route = "execute" if supervisor_report["decision"] == "approve" else "review"
        supervisor_decision = SupervisorDecision(
            route=route,
            severity="info" if route == "execute" else "warning",
            summary=str(supervisor_report["reasoning_summary"]),
        )

        review = self.core._build_review(market, targets, suggestions, risk_reasons)
        llm_review = self.llm.review_cycle(
            review=review,
            market=market,
            signals=signals,
            orders=[],
            events=critic_events,
            memory_context=memory_summary,
            extra_context={
                "supervisor_decision": supervisor_report,
                "execution_report": execution_report,
            },
        )
        if llm_review is not None:
            review = llm_review
        review_report = {
            "summary": review.summary,
            "risk_notes": review.risk_notes,
            "metrics": review.metrics,
        }
        evolution = self.llm.propose_evolution(
            market=market,
            scores=scores,
            review=review,
            events=critic_events,
            memory_context=memory_summary,
            extra_context={"portfolio_mode": self.portfolio_mode},
        ) or [
            EvolutionExperiment(
                name="fund_regime_tuning",
                hypothesis="Adjust regime-match weights after observing more daily cycles.",
                validation_plan="Collect 20+ daily fund cycles before reweighting regime-match logic.",
            )
        ]
        blackboard = {
            "market_report": market_report,
            "factor_report": factor_report,
            "portfolio_report": portfolio_report,
            "risk_report": risk_report,
            "execution_report": execution_report,
            "review_report": review_report,
            "memory_context": memory_summary,
            "supervisor_decision": supervisor_report,
        }
        trace = self._agent_trace(market_report, factor_report, portfolio_report, risk_report, execution_report, review_report, supervisor_decision)
        events = self._events(market_report, factor_report, portfolio_report, risk_report, execution_report, review_report, critic_events, supervisor_decision)
        messages = self._agent_messages(market_report, factor_report, portfolio_report, risk_report, execution_report, review_report, supervisor_report)
        self.memory.append(
            cycle_id=cycle_id,
            market=market,
            review=review,
            event_count=len(events),
            trace_count=len(trace),
        )
        return CycleResult(
            cycle_id=cycle_id,
            market=market,
            scores=scores,
            signals=signals,
            targets=targets,
            orders=[],
            suggestions=suggestions,
            review=review,
            evolution=evolution,
            workflow=self.framework,
            agent_trace=trace,
            collaboration_events=events,
            agent_messages=messages,
            blackboard=to_jsonable(blackboard),
        )

    def _agent_trace(
        self,
        market_report: dict[str, Any],
        factor_report: dict[str, Any],
        portfolio_report: dict[str, Any],
        risk_report: dict[str, Any],
        execution_report: dict[str, Any],
        review_report: dict[str, Any],
        supervisor_decision: SupervisorDecision,
    ) -> list[AgentStep]:
        trace = self.core._agent_trace(market_report, factor_report, portfolio_report, risk_report, execution_report, review_report)
        return [
            AgentStep(
                name="FundMarketDetectAgent",
                role=trace[0].role,
                framework=self.framework,
                model=f"deterministic benchmark regime rules + LLM({self.llm.model})" if self.llm.enabled else trace[0].model,
                tools=["benchmark_index.csv", "llm_fund_market_regime"],
                summary=market_report.get("llm_commentary", trace[0].summary),
                metrics=trace[0].metrics,
                next_action="FundFactorAgent",
            ),
            AgentStep(
                name="FundFactorAgent",
                role=trace[1].role,
                framework=self.framework,
                model=f"deterministic multi-factor scoring + LLM({self.llm.model})" if self.llm.enabled else trace[1].model,
                tools=["fund_nav_daily.csv", "fund_metadata.csv", "llm_fund_factor_ranking"],
                summary=factor_report.get("llm_summary", trace[1].summary),
                metrics=trace[1].metrics,
                next_action="FundPortfolioAgent",
            ),
            AgentStep(
                name="FundPortfolioAgent",
                role=trace[2].role,
                framework=self.framework,
                model=trace[2].model,
                tools=trace[2].tools,
                summary=trace[2].summary,
                metrics=trace[2].metrics,
                next_action="FundRiskAgent",
            ),
            AgentStep(
                name="FundRiskAgent",
                role=trace[3].role,
                framework=self.framework,
                model=trace[3].model,
                tools=trace[3].tools,
                status=trace[3].status,
                summary=trace[3].summary,
                metrics=trace[3].metrics,
                next_action="FundSupervisorAgent",
            ),
            AgentStep(
                name="FundSupervisorAgent",
                role="多智能体仲裁与路由",
                framework=self.framework,
                model=f"supervisory routing policy + LLM({self.llm.model})" if self.llm.enabled else "supervisory routing policy",
                tools=["critic_events", "risk_guardrails", "llm_fund_supervisor"],
                status="ok" if supervisor_decision.route == "execute" else "warning",
                summary=supervisor_decision.summary,
                metrics={"route_execute": 1.0 if supervisor_decision.route == "execute" else 0.0},
                next_action="FundExecutionAgent" if supervisor_decision.route == "execute" else "FundReviewAgent",
            ),
            AgentStep(
                name="FundExecutionAgent",
                role=trace[4].role,
                framework=self.framework,
                model=trace[4].model,
                tools=trace[4].tools,
                summary=trace[4].summary,
                metrics=trace[4].metrics,
                next_action="FundReviewAgent",
            ),
            AgentStep(
                name="FundReviewAgent",
                role=trace[5].role,
                framework=self.framework,
                model=f"deterministic review summary + LLM({self.llm.model})" if self.llm.enabled else trace[5].model,
                tools=["risk_report", "execution_report", "llm_review"],
                summary=str(review_report["summary"]),
                metrics={str(key): float(value) for key, value in dict(review_report["metrics"]).items()},
                next_action="end",
            ),
        ]

    def _events(
        self,
        market_report: dict[str, Any],
        factor_report: dict[str, Any],
        portfolio_report: dict[str, Any],
        risk_report: dict[str, Any],
        execution_report: dict[str, Any],
        review_report: dict[str, Any],
        critic_events: list[CollaborationEvent],
        supervisor_decision: SupervisorDecision,
    ) -> list[CollaborationEvent]:
        base_events = self.core._collaboration_events(
            market_report,
            factor_report,
            portfolio_report,
            risk_report,
            execution_report,
            review_report,
        )
        return [
            *base_events[:4],
            *critic_events,
            CollaborationEvent(
                agent="FundSupervisorAgent",
                kind="review_summary",
                severity=supervisor_decision.severity,
                summary=supervisor_decision.summary,
                payload={"route": supervisor_decision.route},
            ),
            *base_events[4:],
        ]

    def _agent_messages(
        self,
        market_report: dict[str, Any],
        factor_report: dict[str, Any],
        portfolio_report: dict[str, Any],
        risk_report: dict[str, Any],
        execution_report: dict[str, Any],
        review_report: dict[str, Any],
        supervisor_report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        state: dict[str, Any] = {"agent_messages": []}
        payloads = [
            ("FundMarketDetectAgent", "基金市场状态识别", market_report, market_report.get("llm_commentary", market_report["agent_explanation"])),
            ("FundFactorAgent", "基金因子研究与排序解释", factor_report, factor_report.get("llm_summary", factor_report["agent_explanation"])),
            ("FundPortfolioAgent", "组合构建与目标权重提案", portfolio_report, portfolio_report["agent_explanation"]),
            ("FundRiskAgent", "硬规则风控审查", risk_report, risk_report["agent_explanation"]),
            ("FundSupervisorAgent", "多智能体仲裁与路由", supervisor_report, supervisor_report["reasoning_summary"]),
            ("FundExecutionAgent", "调仓建议生成", execution_report, execution_report["agent_explanation"]),
            ("FundReviewAgent", "审查总结", review_report, str(review_report["summary"])),
        ]
        for agent_name, role, output, summary in payloads:
            state["agent_messages"] = append_agent_message(
                state,
                {
                    "agent_name": agent_name,
                    "role": role,
                    "summary": summary,
                    "output": to_jsonable(output),
                },
            )
        return list(state["agent_messages"])
