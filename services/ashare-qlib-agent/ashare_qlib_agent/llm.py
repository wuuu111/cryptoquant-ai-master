from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from typing import TYPE_CHECKING
from typing import Any

import httpx

from .schemas import (
    CollaborationEvent,
    EvolutionExperiment,
    FactorScore,
    MarketRegimeResult,
    OrderIntent,
    ReviewReport,
    Signal,
    TargetPosition,
)

if TYPE_CHECKING:
    from .settings import RuntimeSettings


MULTI_AGENT_SYSTEM_PROMPT = """
你是 A 股 Qlib + LangGraph 多 Agent 量化投研系统的一名专业智能体。

全局原则：
- 规则系统负责确定性计算；LLM 负责解释、质疑、假设、协作和进化。
- LLM 不得替代 Qlib 回测、组合优化、硬风控、下单规则。
- LLM 不得直接下单，不得直接决定买卖，不得绕过 RiskAgent hard block 或 DataAgent data quality fail。
- 所有 LLM 输出必须是结构化 JSON，不要输出 Markdown、自然语言段落或额外解释。
- 只能基于输入 payload 判断，不得编造行情、交易、回测、历史经验或因子表现。
- 新因子只能作为 candidate_pool 或 shadow_test 候选，未验证前不得进入实盘主策略。
- 如果证据不足，必须降低 confidence 并写入 warnings。
- 如果出现冲突，SupervisorAgent 必须优先尊重数据质量、硬风控和订单审查结论。
""".strip()


class LLMClient:
    """Small OpenAI-compatible chat client for advisory agent reasoning."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        enabled: bool,
        timeout: float = 45.0,
        retries: int = 1,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled and bool(api_key)
        self.timeout = timeout
        self.retries = max(0, retries)
        self._soft_disabled = False
        self._soft_disable_reason = ""

    @classmethod
    def from_env(cls) -> "LLMClient":
        load_dotenv()
        api_key = (
            os.getenv("ASHARE_LLM_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        return cls(
            api_key=api_key,
            model=os.getenv("ASHARE_LLM_MODEL", "deepseek-v4-flash"),
            base_url=os.getenv("ASHARE_LLM_BASE_URL", "https://api.deepseek.com"),
            enabled=os.getenv("ASHARE_LLM_ENABLED", "1").lower() not in {"0", "false", "no"},
            timeout=float(os.getenv("ASHARE_LLM_TIMEOUT", "8")),
            retries=int(os.getenv("ASHARE_LLM_RETRIES", "0")),
        )

    @classmethod
    def from_settings(cls, settings: "RuntimeSettings") -> "LLMClient":
        load_dotenv()
        graph = settings.fund_graph
        api_key = (
            graph.llm_api_key
            or os.getenv("ASHARE_LLM_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        model = graph.llm_model or os.getenv("ASHARE_LLM_MODEL", "deepseek-v4-flash")
        base_url = graph.llm_base_url or os.getenv("ASHARE_LLM_BASE_URL", "https://api.deepseek.com")
        enabled = graph.llm_enabled
        timeout = float(graph.llm_timeout or os.getenv("ASHARE_LLM_TIMEOUT", "8"))
        retries = int(graph.llm_retries if graph.llm_retries is not None else int(os.getenv("ASHARE_LLM_RETRIES", "0")))
        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url,
            enabled=enabled,
            timeout=timeout,
            retries=retries,
        )

    @property
    def status(self) -> str:
        return "enabled" if self.enabled else "disabled"

    def _system_prompt(self, role_prompt: str) -> str:
        return f"{MULTI_AGENT_SYSTEM_PROMPT}\n\n当前智能体任务：\n{role_prompt.strip()}"

    def detect_market_regime(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化系统中的 MarketDetectAgent，负责识别当前市场状态。"
                "你只能基于输入数据判断，不得编造市场信息。输出严格 JSON。"
            ),
            task="detect_market_regime",
            payload=payload,
            schema={
                "market_regime": "",
                "risk_appetite": "",
                "liquidity_state": "",
                "dominant_styles": [],
                "weakening_styles": [],
                "dominant_industries": [],
                "suitable_factor_types": [],
                "unsuitable_factor_types": [],
                "risk_warnings": [],
                "evidence": [],
                "confidence": 0.0,
            },
            fallback=_market_regime_fallback(),
        )

    def retrieve_memory_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化系统中的历史经验检索官。只能总结输入中的历史记忆、复盘、回测或交易记录，"
                "不得凭空生成历史经验。输出严格 JSON。"
            ),
            task="retrieve_memory_context",
            payload=payload,
            schema={
                "similar_cases": [],
                "recent_failures": [],
                "risk_reminders": [],
                "confidence": 0.0,
                "warnings": [],
            },
            fallback={
                "similar_cases": [],
                "recent_failures": [],
                "risk_reminders": [],
                "confidence": 0.2,
                "warnings": ["No sufficient historical memory found."],
            },
        )

    def diagnose_model_prediction(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化系统中的模型研究员。你只能诊断模型预测分布、可信度和风险，"
                "不得修改模型分数或直接给买卖指令。输出严格 JSON。"
            ),
            task="diagnose_model_prediction",
            payload=payload,
            schema={
                "model_prediction_summary": {},
                "model_confidence": 0.0,
                "model_risk": [],
                "suggested_action": "allow | allow_but_reduce_weight | pause | require_review",
                "evidence": [],
                "confidence": 0.0,
            },
            fallback={
                "model_prediction_summary": payload.get("model_prediction_summary", {}),
                "model_confidence": 0.3,
                "model_risk": ["LLM model diagnosis failed or disabled; using deterministic prediction statistics."],
                "suggested_action": "allow_but_reduce_weight",
                "evidence": [],
                "confidence": 0.3,
            },
        )

    def generate_factor_candidates(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化系统中的 FactorAgent，负责基于当前市场状态提出可回测、可解释、无未来函数的候选因子。"
                "你不能直接给买卖建议。你只能生成因子假设和 Qlib 表达式，最终表现必须交由回测系统验证。"
                "不得使用未来数据，不得生成不可解释的复杂表达式。输出严格 JSON。"
            ),
            task="generate_factor_candidates",
            payload=payload,
            schema={
                "factor_candidates": [
                    {
                        "factor_name": "",
                        "hypothesis": "",
                        "applicable_regime": [],
                        "qlib_expression": "",
                        "expected_alpha_source": "",
                        "risk_exposure": [],
                        "neutralization_required": [],
                        "failure_modes": [],
                        "required_tests": [],
                        "confidence": 0.0,
                    }
                ],
                "factors_to_reduce": [],
                "factors_to_retire": [],
                "mutation_suggestions": [],
            },
            fallback={"factor_candidates": [], "factors_to_reduce": [], "factors_to_retire": [], "mutation_suggestions": []},
        )

    def explain_portfolio(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化系统中的组合解释员。你只能解释确定性组合结果并提出约束建议，"
                "不得直接修改仓位。输出严格 JSON。"
            ),
            task="explain_portfolio",
            payload=payload,
            schema={
                "portfolio_summary": "",
                "concentration_risk": "",
                "style_exposure_comment": "",
                "constraint_suggestions": [],
                "warnings": [],
                "confidence": 0.0,
            },
            fallback={
                "portfolio_summary": "Deterministic portfolio construction completed.",
                "concentration_risk": "See deterministic exposure metrics.",
                "style_exposure_comment": "",
                "constraint_suggestions": [],
                "warnings": ["LLM portfolio explanation failed or disabled."],
                "confidence": 0.3,
            },
        )

    def explain_risk(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化系统中的软风险解释员。硬风控结果不可被你覆盖，"
                "只能解释风险来源和建议动作。输出严格 JSON。"
            ),
            task="explain_risk",
            payload=payload,
            schema={
                "hard_risk_check": {"passed": True, "blocking_reasons": []},
                "soft_risk_analysis": {
                    "llm_detected_risks": [],
                    "risk_level": "low | medium | high",
                    "recommended_action": "allow | reduce_position | rebalance | pause",
                },
                "confidence": 0.0,
            },
            fallback={
                "hard_risk_check": payload.get("hard_risk_check", {"passed": True, "blocking_reasons": []}),
                "soft_risk_analysis": {
                    "llm_detected_risks": ["LLM risk explanation failed or disabled."],
                    "risk_level": "medium",
                    "recommended_action": "allow" if payload.get("hard_risk_check", {}).get("passed", True) else "pause",
                },
                "confidence": 0.3,
            },
        )

    def explain_fund_market_regime(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是基金轮动系统中的 FundMarketDetectAgent。"
                "你只能解释市场门控和基金语境下的 regime 判断，不得编造行情。输出严格 JSON。"
            ),
            task="explain_fund_market_regime",
            payload=payload,
            schema={
                "regime_commentary": "",
                "risk_flags": [],
                "confidence": 0.0,
            },
            fallback={
                "regime_commentary": str(payload.get("reason", "Deterministic fund regime detection completed.")),
                "risk_flags": [],
                "confidence": 0.3,
            },
        )

    def explain_fund_factor_ranking(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是基金轮动系统中的 FundFactorAgent。"
                "你只能解释基金排序结果和争议点，不得直接修改分数。输出严格 JSON。"
            ),
            task="explain_fund_factor_ranking",
            payload=payload,
            schema={
                "ranking_summary": "",
                "supporting_funds": [],
                "opposing_funds": [],
                "confidence": 0.0,
            },
            fallback={
                "ranking_summary": "Deterministic fund ranking completed.",
                "supporting_funds": [],
                "opposing_funds": [],
                "confidence": 0.3,
            },
        )

    def supervise_fund_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是基金多 Agent 投委会主席。"
                "只能基于基金流程中的市场、评分、组合、风控和 critic 信息做裁决。"
                "硬风控失败不可绕过。输出严格 JSON。"
            ),
            task="supervise_fund_decision",
            payload=payload,
            schema={
                "decision": "approve | reduce | pause | reject | request_revision",
                "reasoning_summary": "",
                "supporting_evidence": [],
                "opposing_evidence": [],
                "required_modifications": [],
                "agents_to_reinvoke": [],
                "requires_human_review": False,
                "confidence": 0.0,
            },
            fallback={
                "decision": "approve",
                "reasoning_summary": "LLM fund supervisor unavailable; deterministic guardrails decide the route.",
                "supporting_evidence": [],
                "opposing_evidence": [],
                "required_modifications": [],
                "agents_to_reinvoke": [],
                "requires_human_review": False,
                "confidence": 0.2,
            },
        )

    def critique_orders(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化系统中的交易审查官。检查订单与 alpha、组合、风控、市场状态是否一致。"
                "你不能下单，也不能绕过硬风控。输出严格 JSON。"
            ),
            task="critique_orders",
            payload=payload,
            schema={
                "decision": "pass | revise_orders | block",
                "order_level_flags": [],
                "portfolio_level_flags": [],
                "risk_summary": "",
                "confidence": 0.0,
            },
            fallback={
                "decision": "block" if any(item.get("blocked") for item in payload.get("order_list", [])) else "pass",
                "order_level_flags": [],
                "portfolio_level_flags": [],
                "risk_summary": "LLM order critique failed or disabled; deterministic order checks remain active.",
                "confidence": 0.3,
            },
        )

    def supervise_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化多 Agent 投委会主席。读取所有 Agent 报告后给出流程仲裁。"
                "DataAgent 数据质量失败、RiskAgent 硬风控失败、OrderCritic block 都不可被批准绕过。输出严格 JSON。"
            ),
            task="supervise_decision",
            payload=payload,
            schema={
                "decision": "approve | reduce | pause | reject | request_revision",
                "reasoning_summary": "",
                "supporting_evidence": [],
                "opposing_evidence": [],
                "required_modifications": [],
                "agents_to_reinvoke": [],
                "requires_human_review": False,
                "confidence": 0.0,
            },
            fallback={
                "decision": "approve",
                "reasoning_summary": "LLM supervisor unavailable; deterministic guardrails will decide final route.",
                "supporting_evidence": [],
                "opposing_evidence": [],
                "required_modifications": [],
                "agents_to_reinvoke": [],
                "requires_human_review": False,
                "confidence": 0.2,
            },
        )

    def structure_memory_write(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._advisory_json(
            system=(
                "你是 A 股量化系统中的结构化知识库管理员。只能把输入中的复盘、风控、执行、因子证据转成可检索经验，"
                "不得写入无证据或纯主观评论。输出严格 JSON。"
            ),
            task="structure_memory_write",
            payload=payload,
            schema={
                "memory_candidates": [
                    {
                        "memory_type": "factor_lesson | regime_lesson | risk_lesson | execution_lesson",
                        "trigger": "",
                        "evidence": "",
                        "lesson": "",
                        "valid_regime": "",
                        "expiry_condition": "",
                        "confidence": 0.0,
                    }
                ]
            },
            fallback={"memory_candidates": []},
        )

    def critique_pre_execution(
        self,
        *,
        market: MarketRegimeResult,
        targets: list[TargetPosition],
        signals: list[Signal],
        existing_events: list[CollaborationEvent],
        memory_context: dict[str, Any] | list[dict[str, Any]],
        blackboard_context: dict[str, Any] | None = None,
    ) -> list[CollaborationEvent]:
        if not self.enabled:
            return []
        payload = self._complete_json(
            system=(
                "You are an independent A-share trading risk critic. "
                "Find contradictions, missing checks, and reasons to pause. "
                "Never approve bypassing hard constraints. Return strict JSON."
            ),
            user={
                "task": "critique_pre_execution",
                "market": asdict(market),
                "targets": [asdict(item) for item in targets[:20]],
                "signals": [asdict(item) for item in signals[:20]],
                "existing_events": [asdict(item) for item in existing_events[-12:]],
                "memory_context": _compact_memory_context(memory_context),
                "blackboard_context": blackboard_context or {},
                "schema": {
                    "events": [
                        {
                            "kind": "llm_objection | llm_warning | llm_note",
                            "severity": "blocker | warning | info",
                            "summary": "short Chinese or English summary",
                            "payload": {"reason": "brief evidence"},
                        }
                    ]
                },
            },
            fallback={"events": []},
        )
        return self._events_from_payload("LLMCriticAgent", payload)

    def review_cycle(
        self,
        *,
        review: ReviewReport,
        market: MarketRegimeResult,
        signals: list[Signal],
        orders: list[OrderIntent],
        events: list[CollaborationEvent],
        memory_context: dict[str, Any] | list[dict[str, Any]],
        extra_context: dict[str, Any] | None = None,
    ) -> ReviewReport | None:
        if not self.enabled:
            return None
        payload = self._complete_json(
            system=(
                "你是 A 股影子交易系统的资深量化复盘分析师。"
                "必须使用简体中文撰写复盘摘要和风险提示，不得混入英文句子。"
                "复盘必须简洁、可用于决策，不得编造交易。只返回严格 JSON。"
            ),
            user={
                "task": "review_cycle",
                "baseline_review": asdict(review),
                "market": asdict(market),
                "signals": [asdict(item) for item in signals[:20]],
                "orders": [asdict(item) for item in orders[:20]],
                "collaboration_events": [asdict(item) for item in events[-20:]],
                "memory_context": _compact_memory_context(memory_context),
                "extra_context": extra_context or {},
                "schema": {
                    "summary": "一段中文复盘摘要",
                    "risk_notes": ["中文风险提示"],
                    "metrics": {"llm_review_used": 1.0},
                },
            },
            fallback={},
        )
        summary = str(payload.get("summary", "")).strip()
        if not summary:
            return None
        risk_notes = payload.get("risk_notes", [])
        if not isinstance(risk_notes, list):
            risk_notes = []
        metrics = dict(review.metrics)
        for key, value in dict(payload.get("metrics", {})).items():
            try:
                metrics[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        metrics["llm_review_used"] = 1.0
        return ReviewReport(
            summary=summary,
            risk_notes=[str(item) for item in risk_notes[:8]] or review.risk_notes,
            metrics=metrics,
        )

    def propose_evolution(
        self,
        *,
        market: MarketRegimeResult,
        scores: list[FactorScore],
        review: ReviewReport,
        events: list[CollaborationEvent],
        memory_context: dict[str, Any] | list[dict[str, Any]],
        extra_context: dict[str, Any] | None = None,
    ) -> list[EvolutionExperiment]:
        if not self.enabled:
            return []
        payload = self._complete_json(
            system=(
                "You are a quant research lead proposing safe A-share strategy experiments. "
                "Experiments must require validation and human approval before deployment. Return strict JSON."
            ),
            user={
                "task": "propose_evolution",
                "market": asdict(market),
                "top_scores": [asdict(item) for item in scores[:10]],
                "review": asdict(review),
                "collaboration_events": [asdict(item) for item in events[-20:]],
                "memory_context": _compact_memory_context(memory_context),
                "extra_context": extra_context or {},
                "schema": {
                    "experiments": [
                        {
                            "name": "short-kebab-name",
                            "hypothesis": "testable hypothesis",
                            "validation_plan": "walk-forward/shadow validation plan",
                            "approval_required": True,
                        }
                    ]
                },
            },
            fallback={"experiments": []},
        )
        experiments = []
        for item in payload.get("experiments", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            hypothesis = str(item.get("hypothesis", "")).strip()
            validation_plan = str(item.get("validation_plan", "")).strip()
            if not name or not hypothesis or not validation_plan:
                continue
            experiments.append(EvolutionExperiment(
                name=name[:80],
                hypothesis=hypothesis[:500],
                validation_plan=validation_plan[:700],
                approval_required=bool(item.get("approval_required", True)),
            ))
        return experiments[:3]

    def _advisory_json(
        self,
        *,
        system: str,
        task: str,
        payload: dict[str, Any],
        schema: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        return self._complete_json(
            system=system,
            user={"task": task, "payload": payload, "schema": schema},
            fallback=fallback,
        )

    def _complete_json(self, *, system: str, user: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return fallback
        if self._soft_disabled:
            result = dict(fallback)
            result["_llm_error"] = self._soft_disable_reason or "LLM disabled for the remainder of this cycle."
            return result
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt(system)},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        last_error = ""
        raw_response = ""
        for attempt in range(self.retries + 1):
            try:
                request_body = dict(body)
                if attempt > 0:
                    request_body.pop("response_format", None)
                response = httpx.post(url, headers=headers, json=request_body, timeout=self.timeout)
                if response.status_code == 400 and "response_format" in request_body:
                    request_body.pop("response_format", None)
                    response = httpx.post(url, headers=headers, json=request_body, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                raw_response = str(data["choices"][0]["message"]["content"])
                parsed = safe_json_parse(raw_response, fallback=fallback)
                if "_parse_error" not in parsed:
                    return parsed
                last_error = str(parsed.get("_parse_error", "JSON parse failed"))
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:180]}"
        result = dict(fallback)
        self._soft_disabled = True
        self._soft_disable_reason = last_error or "LLM call failed"
        result["_llm_error"] = self._soft_disable_reason
        if raw_response:
            result["raw_response"] = raw_response[:2000]
        return result

    @staticmethod
    def _events_from_payload(agent: str, payload: dict[str, Any]) -> list[CollaborationEvent]:
        events = []
        for item in payload.get("events", []):
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "info")).lower()
            if severity not in {"blocker", "warning", "info"}:
                severity = "info"
            summary = str(item.get("summary", "")).strip()
            if not summary:
                continue
            payload_value = item.get("payload", {})
            if not isinstance(payload_value, dict):
                payload_value = {"value": str(payload_value)}
            events.append(CollaborationEvent(
                agent=agent,
                kind=str(item.get("kind", "llm_note")),
                severity=severity,
                summary=summary[:500],
                payload=payload_value,
            ))
        if payload.get("_llm_error"):
            events.append(CollaborationEvent(
                agent=agent,
                kind="llm_error",
                severity="warning",
                summary="LLM call failed; deterministic collaboration checks remain active.",
                payload={"error": payload["_llm_error"]},
            ))
        return events[:5]


def safe_json_parse(content: str, fallback: dict[str, Any]) -> dict[str, Any]:
    """Parse strict or embedded JSON object, preserving raw output on failure."""
    raw = str(content or "")
    for candidate in (_strip_json_fence(raw), _extract_json_object(raw)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    result = dict(fallback)
    result["raw_response"] = raw[:2000]
    result["_parse_error"] = "LLM response did not contain a valid JSON object."
    return result


def _extract_json_object(content: str) -> str:
    text = _strip_json_fence(content)
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else ""


def _market_regime_fallback() -> dict[str, Any]:
    return {
        "market_regime": "unknown_or_rule_based",
        "risk_appetite": "neutral",
        "liquidity_state": "unknown",
        "dominant_styles": [],
        "weakening_styles": [],
        "dominant_industries": [],
        "suitable_factor_types": [],
        "unsuitable_factor_types": [],
        "risk_warnings": ["LLM market regime detection failed, fallback to rule-based output."],
        "evidence": [],
        "confidence": 0.3,
    }


def _compact_memory_context(memory_context: Any) -> Any:
    if isinstance(memory_context, list):
        return memory_context[-5:]
    if isinstance(memory_context, dict):
        return memory_context
    return []


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def load_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE lines without overriding existing env vars."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
