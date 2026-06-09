from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .schemas import (
    CollaborationEvent,
    FactorScore,
    MarketRegimeResult,
    OrderIntent,
    ReviewReport,
    Signal,
    TargetPosition,
)


@dataclass(frozen=True)
class SupervisorDecision:
    route: str
    summary: str
    severity: str = "info"


class AgentMemoryStore:
    """Small append-only memory for cycle summaries.

    This is intentionally simple: the LangGraph state gets recent summaries as
    context, and the final cycle writes back a compact JSONL record.
    """

    def __init__(self, registry_dir: str | Path):
        self.memory_dir = Path(registry_dir) / "memory"
        self.path = self.memory_dir / "cycles.jsonl"

    def recent(self, limit: int = 5) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    def append(
        self,
        *,
        cycle_id: str,
        market: MarketRegimeResult,
        review: ReviewReport,
        event_count: int,
        trace_count: int,
    ) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "cycle_id": cycle_id,
            "regime": market.regime,
            "gate": market.gate,
            "market_score": market.score,
            "summary": review.summary,
            "event_count": event_count,
            "trace_count": trace_count,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def append_structured(self, cycle_id: str, candidates: list[dict[str, Any]]) -> int:
        if not candidates:
            return 0
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        path = self.memory_dir / "lessons.jsonl"
        written = 0
        existing = set()
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    existing.add((item.get("memory_type"), item.get("trigger"), item.get("lesson")))
        with path.open("a", encoding="utf-8") as handle:
            for candidate in candidates:
                key = (candidate.get("memory_type"), candidate.get("trigger"), candidate.get("lesson"))
                if key in existing:
                    continue
                handle.write(json.dumps({"cycle_id": cycle_id, **candidate}, ensure_ascii=False) + "\n")
                existing.add(key)
                written += 1
        return written


class CriticAgent:
    """Independent consistency checker for the shared blackboard."""

    def __init__(self, max_position_weight: float = 0.20):
        self.max_position_weight = max_position_weight

    def critique_pre_execution(
        self,
        *,
        market: MarketRegimeResult,
        targets: list[TargetPosition],
        signals: list[Signal],
        market_advice: dict[str, Any],
    ) -> list[CollaborationEvent]:
        events: list[CollaborationEvent] = []
        target_exposure = sum(item.target_weight for item in targets)

        if market.gate == "BLOCK_NEW_RISK" and targets:
            events.append(CollaborationEvent(
                agent="CriticAgent",
                kind="pre_execution_objection",
                severity="blocker",
                summary="Market gate blocks new risk, but target positions exist.",
                payload={"target_count": len(targets), "target_exposure": target_exposure},
            ))

        if target_exposure > market.exposure_multiplier + 1e-6:
            events.append(CollaborationEvent(
                agent="CriticAgent",
                kind="pre_execution_objection",
                severity="warning",
                summary="Target exposure is above market exposure multiplier.",
                payload={"target_exposure": target_exposure, "allowed_exposure": market.exposure_multiplier},
            ))

        oversized = [item.symbol for item in targets if item.target_weight > self.max_position_weight + 1e-6]
        if oversized:
            events.append(CollaborationEvent(
                agent="CriticAgent",
                kind="pre_execution_objection",
                severity="blocker",
                summary="One or more targets exceed max position weight.",
                payload={"symbols": oversized[:10]},
            ))

        model_risk = float(market_advice.get("risk_off_probability", 0.0)) if market_advice.get("available") else 0.0
        if model_risk >= 0.70 and targets:
            events.append(CollaborationEvent(
                agent="CriticAgent",
                kind="model_disagreement",
                severity="warning",
                summary="Market model shows high risk-off probability while portfolio still has targets.",
                payload={"risk_off_probability": model_risk, "target_count": len(targets)},
            ))

        if not events:
            events.append(CollaborationEvent(
                agent="CriticAgent",
                kind="pre_execution_check",
                severity="info",
                summary="No pre-execution objections.",
                payload={"target_count": len(targets), "signal_count": len(signals)},
            ))
        return events

    def critique_orders(self, orders: list[OrderIntent]) -> list[CollaborationEvent]:
        blocked = [item for item in orders if item.blocked]
        if not orders:
            return [CollaborationEvent(
                agent="CriticAgent",
                kind="order_check",
                severity="info",
                summary="No orders to critique.",
                payload={"order_count": 0},
            )]
        if blocked:
            return [CollaborationEvent(
                agent="CriticAgent",
                kind="order_objection",
                severity="warning",
                summary="Some generated orders are blocked and require review.",
                payload={"blocked_orders": len(blocked), "order_count": len(orders)},
            )]
        return [CollaborationEvent(
            agent="CriticAgent",
            kind="order_check",
            severity="info",
            summary="Orders passed critic consistency checks.",
            payload={"order_count": len(orders)},
        )]


class SupervisorAgent:
    """Route the graph after multiple agents publish to the blackboard."""

    def apply_guardrails(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply non-bypassable deterministic guardrails to an LLM or rule decision."""
        llm_decision = payload.get("llm_decision", {})
        if not isinstance(llm_decision, dict):
            llm_decision = {}

        decision = str(llm_decision.get("decision", "pause")).lower()
        if decision not in {"approve", "reduce", "pause", "reject", "request_revision"}:
            decision = "pause"

        opposing: list[str] = []
        data_quality = payload.get("data_quality_report", {})
        if isinstance(data_quality, dict) and data_quality.get("data_passed") is False:
            reasons = data_quality.get("blocking_reasons") or data_quality.get("warnings") or []
            opposing.append(f"Data quality failed: {', '.join(map(str, reasons)) or 'unknown reason'}")

        if payload.get("hard_risk_passed") is False:
            risk_report = payload.get("risk_report", {})
            hard_check = risk_report.get("hard_risk_check", {}) if isinstance(risk_report, dict) else {}
            reasons = hard_check.get("blocking_reasons", []) if isinstance(hard_check, dict) else []
            opposing.append(f"Hard risk failed: {', '.join(map(str, reasons)) or 'unknown reason'}")

        order_report = payload.get("order_critic_report", {})
        if isinstance(order_report, dict) and order_report.get("decision") == "block":
            opposing.append(f"Order critic blocked orders: {order_report.get('risk_summary', 'review required')}")

        critic_report = payload.get("critic_report", {})
        if isinstance(critic_report, dict) and int(critic_report.get("blockers", 0) or 0) > 0:
            opposing.append(f"Critic raised {critic_report.get('blockers')} blocker(s).")

        if opposing and decision == "approve":
            decision = "pause"

        requires_review = bool(opposing) or bool(llm_decision.get("requires_human_review", False)) or decision in {
            "reduce",
            "pause",
            "reject",
            "request_revision",
        }
        return {
            "decision": decision,
            "reasoning_summary": str(llm_decision.get("reasoning_summary") or llm_decision.get("summary") or "Supervisor applied deterministic guardrails."),
            "supporting_evidence": list(llm_decision.get("supporting_evidence", []) or []),
            "opposing_evidence": [*list(llm_decision.get("opposing_evidence", []) or []), *opposing],
            "required_modifications": list(llm_decision.get("required_modifications", []) or []),
            "agents_to_reinvoke": list(llm_decision.get("agents_to_reinvoke", []) or []),
            "requires_human_review": requires_review,
            "confidence": float(llm_decision.get("confidence", 0.4) or 0.4),
        }

    def decide_after_risk(
        self,
        *,
        targets: list[TargetPosition],
        events: list[CollaborationEvent],
    ) -> SupervisorDecision:
        blockers = [item for item in events if item.severity == "blocker"]
        if blockers:
            return SupervisorDecision(
                route="review",
                severity="blocker",
                summary=f"Supervisor routed to review because {len(blockers)} blocker event(s) were raised.",
            )
        if not targets:
            return SupervisorDecision(
                route="review",
                summary="Supervisor routed to review because there are no approved targets.",
            )
        return SupervisorDecision(
            route="execute",
            summary=f"Supervisor routed {len(targets)} approved target(s) to execution.",
        )

    def final_event(self, decision: SupervisorDecision) -> CollaborationEvent:
        return CollaborationEvent(
            agent="SupervisorAgent",
            kind="route_decision",
            severity=decision.severity,
            summary=decision.summary,
            payload={"route": decision.route},
        )


def event_to_dict(event: CollaborationEvent) -> dict[str, Any]:
    return asdict(event)
