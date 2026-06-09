from __future__ import annotations

from .schemas import MarketRegimeResult, OrderIntent, ReviewReport, Signal


class ReviewAgent:
    """Create a compact review artifact for audit pages and later learning."""

    def build_review(
        self,
        market: MarketRegimeResult,
        signals: list[Signal],
        orders: list[OrderIntent],
    ) -> ReviewReport:
        actionable = [item for item in signals if item.action != "HOLD"]
        blocked_orders = [item for item in orders if item.blocked]
        target_exposure = sum(max(0.0, item.target_weight) for item in actionable)
        risk_notes: list[str] = []
        if market.gate != "ALLOW_FULL":
            risk_notes.append(_localize_market_reason(market.reason))
        if blocked_orders:
            risk_notes.append(f"{len(blocked_orders)} 笔订单被执行约束阻断。")
        if target_exposure > 0.8:
            risk_notes.append("目标敞口偏高，需要复核流动性和持仓集中度。")

        summary = (
            f"{_localize_market_label(market.regime)}/{_localize_market_label(market.gate)}："
            f"本轮有 {len(actionable)} 条可执行信号，{len(orders)} 条订单意图，"
            f"目标敞口 {target_exposure:.1%}。"
        )
        return ReviewReport(
            summary=summary,
            risk_notes=risk_notes,
            metrics={
                "actionable_signals": float(len(actionable)),
                "order_intents": float(len(orders)),
                "blocked_orders": float(len(blocked_orders)),
                "target_exposure": target_exposure,
                "market_score": market.score,
            },
        )


def _localize_market_label(value: str) -> str:
    labels = {
        "RISK_OFF": "风险规避",
        "RISK_ON": "风险偏好",
        "NEUTRAL": "中性",
        "BLOCK_NEW_RISK": "阻断新增风险",
        "ALLOW_REDUCED": "降低敞口",
        "ALLOW_FULL": "允许完整敞口",
    }
    return labels.get(value, value)


def _localize_market_reason(text: str) -> str:
    if not text:
        return "市场状态由规则模型判定。"
    lower = text.lower()
    reasons = []
    if "index drawdown" in lower:
        reasons.append("指数回撤")
    if "poor breadth" in lower:
        reasons.append("市场宽度偏弱")
    if "limit-down pressure" in lower:
        reasons.append("跌停压力")
    probability = ""
    if "risk_off_probability=" in text:
        probability = text.split("risk_off_probability=", 1)[1].split()[0].rstrip(".")
    if reasons and probability:
        return f"{'、'.join(reasons)}触发风险规避，模型风险规避概率为 {probability}。"
    if reasons:
        return f"{'、'.join(reasons)}触发风险规避。"
    return text.replace(", ", "、")
