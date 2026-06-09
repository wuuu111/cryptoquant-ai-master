from __future__ import annotations

from collections import defaultdict

from .schemas import FactorScore, MarketRegimeResult, PortfolioState, Signal, TargetPosition


MODE_BUCKETS = {
    "conservative": {"equity": 0.40, "bond": 0.40, "commodity": 0.10, "cash": 0.10},
    "balanced": {"equity": 0.60, "bond": 0.25, "commodity": 0.10, "cash": 0.05},
    "aggressive": {"equity": 0.80, "bond": 0.10, "commodity": 0.05, "cash": 0.05},
}


class FundPortfolioAgent:
    def build_targets(
        self,
        scores: list[FactorScore],
        market: MarketRegimeResult,
        portfolio: PortfolioState,
        mode: str = "balanced",
    ) -> tuple[list[Signal], list[TargetPosition]]:
        if market.gate == "BLOCK_NEW_RISK" or portfolio.equity <= 0:
            return [], []
        buckets = MODE_BUCKETS.get(mode.lower(), MODE_BUCKETS["balanced"])
        exposure_multiplier = max(0.0, min(1.0, market.exposure_multiplier))
        scores_by_category: dict[str, list[FactorScore]] = defaultdict(list)
        for item in scores:
            scores_by_category[item.industry.lower()].append(item)

        signals: list[Signal] = []
        targets: list[TargetPosition] = []
        for category, bucket_weight in buckets.items():
            bucket_weight *= exposure_multiplier
            ranked = sorted(scores_by_category.get(category, []), key=lambda row: row.combined_score, reverse=True)
            selected = [item for item in ranked if item.combined_score >= 0][:2] or ranked[:1]
            if not selected:
                continue
            target_weight = bucket_weight / len(selected)
            for item in selected:
                bounded_weight = min(target_weight, 0.20)
                reason = f"mode={mode}; category={category}; market={market.regime}; score={item.combined_score:.3f}"
                signals.append(
                    Signal(
                        symbol=item.symbol,
                        action="BUY" if bounded_weight > 0 else "HOLD",
                        confidence=max(0.0, min(100.0, 55.0 + item.combined_score * 12.0)),
                        target_weight=bounded_weight,
                        score=item.combined_score,
                        reason=reason,
                    )
                )
                targets.append(
                    TargetPosition(
                        symbol=item.symbol,
                        target_weight=bounded_weight,
                        target_value=portfolio.equity * bounded_weight,
                        reason=reason,
                    )
                )
        return signals, targets
