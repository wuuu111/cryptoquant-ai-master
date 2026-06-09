from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .schemas import to_jsonable


def build_agent_message(
    *,
    agent_name: str,
    role: str,
    input_summary: str,
    output: dict[str, Any],
    confidence: float = 0.0,
    evidence: list[Any] | None = None,
    warnings: list[str] | None = None,
    requires_human_review: bool = False,
    next_actions: list[str] | None = None,
    decision: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    payload = {
        "agent_name": agent_name,
        "role": role,
        "input_summary": input_summary,
        "output": to_jsonable(output),
        "confidence": _clamp_confidence(confidence),
        "evidence": to_jsonable(evidence or []),
        "warnings": [str(item) for item in (warnings or [])],
        "requires_human_review": bool(requires_human_review),
        "next_actions": [str(item) for item in (next_actions or [])],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if decision:
        payload["decision"] = str(decision)
    if summary:
        payload["summary"] = str(summary)
    return payload


def append_agent_message(state: Mapping[str, Any], message: dict[str, Any]) -> list[dict[str, Any]]:
    return [*state.get("agent_messages", []), message]


def append_error(state: Mapping[str, Any], agent_name: str, error: Any) -> list[dict[str, Any]]:
    return [
        *state.get("errors", []),
        {
            "agent_name": agent_name,
            "error": str(error),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]


def _clamp_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
