from __future__ import annotations

import math
from statistics import mean, pstdev

from .schemas import FactorScore, InstrumentFeature


class FundFactorAgent:
    def score(self, universe: list[InstrumentFeature], market_regime: str = "RANGE") -> list[FactorScore]:
        if not universe:
            return []
        factor_values = [self._factor_row(item, market_regime) for item in universe]
        factor_names = tuple(factor_values[0].keys())
        zscores = self._zscores(universe, factor_values, factor_names)
        rows: list[FactorScore] = []
        for item in universe:
            diagnostics = {name: zscores[name].get(item.symbol, 0.0) for name in factor_names}
            combined = (
                diagnostics["momentum_score"] * 0.30
                + diagnostics["risk_adjusted_return_score"] * 0.20
                + diagnostics["trend_confirmation_score"] * 0.20
                + diagnostics["drawdown_control_score"] * 0.15
                + diagnostics["regime_match_score"] * 0.15
                - diagnostics["overheat_penalty"] * 0.20
            )
            rows.append(
                FactorScore(
                    symbol=item.symbol,
                    industry=item.category,
                    close=item.close,
                    factor_score=combined,
                    model_score=None,
                    combined_score=combined,
                    rank=0,
                    diagnostics=diagnostics,
                    reason=self._reason(diagnostics),
                )
            )

        ranked = sorted(rows, key=lambda item: item.combined_score, reverse=True)
        return [
            FactorScore(
                symbol=item.symbol,
                industry=item.industry,
                close=item.close,
                factor_score=item.factor_score,
                model_score=item.model_score,
                combined_score=item.combined_score,
                rank=index + 1,
                diagnostics=item.diagnostics,
                reason=item.reason,
            )
            for index, item in enumerate(ranked)
        ]

    def _factor_row(self, item: InstrumentFeature, market_regime: str) -> dict[str, float]:
        factors = item.factors
        return_20d = self._safe_float(factors.get("return_20d", 0.0))
        return_60d = self._safe_float(factors.get("return_60d", 0.0))
        return_120d = self._safe_float(factors.get("return_120d", 0.0))
        volatility_60d = max(self._safe_float(factors.get("volatility_60d", 0.0)), 1e-6)
        drawdown_120d = abs(self._safe_float(factors.get("max_drawdown_120d", 0.0)))
        drawdown_60d = abs(self._safe_float(factors.get("max_drawdown_60d", 0.0)))
        ma20 = self._safe_float(factors.get("ma20", 0.0))
        ma60 = self._safe_float(factors.get("ma60", 0.0))
        distance_to_high = self._safe_float(factors.get("distance_to_60d_high", -1.0), default=-1.0)
        short_return = self._safe_float(factors.get("return_5d", 0.0))

        trend = 0.0
        trend += 1.0 if item.close > ma20 > 0 else 0.0
        trend += 1.0 if ma20 > ma60 > 0 else 0.0
        trend += max(0.0, 1.0 + distance_to_high)
        regime_match = 1.0 if self._category_matches_regime(item.category, market_regime) else 0.0
        overheat = max(0.0, short_return - 0.08) + max(0.0, volatility_60d - 0.03) + max(0.0, drawdown_60d - 0.08)

        return {
            "momentum_score": mean([return_20d, return_60d, return_120d]),
            "risk_adjusted_return_score": (return_60d / volatility_60d) + (return_120d / max(drawdown_120d, 1e-6)),
            "drawdown_control_score": -(drawdown_60d + drawdown_120d) / 2.0,
            "trend_confirmation_score": trend,
            "regime_match_score": regime_match,
            "overheat_penalty": overheat,
        }

    def _zscores(
        self,
        universe: list[InstrumentFeature],
        factor_values: list[dict[str, float]],
        factor_names: tuple[str, ...],
    ) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for name in factor_names:
            values = [self._safe_float(row[name]) for row in factor_values]
            avg = mean(values) if values else 0.0
            sigma = pstdev(values) if len(values) > 1 else 0.0
            if sigma <= 1e-12:
                result[name] = {item.symbol: 0.0 for item in universe}
                continue
            result[name] = {
                item.symbol: max(-3.0, min(3.0, (row[name] - avg) / sigma))
                for item, row in zip(universe, factor_values)
            }
        return result

    @staticmethod
    def _category_matches_regime(category: str, market_regime: str) -> bool:
        normalized_category = category.lower()
        normalized_regime = market_regime.lower()
        if normalized_regime in {"risk_off", "bear_trend"}:
            return normalized_category in {"bond", "cash", "money_market"}
        if normalized_regime == "bull_trend":
            return normalized_category in {"equity", "qdii"}
        return normalized_category in {"equity", "bond", "commodity", "cash", "qdii"}

    @staticmethod
    def _reason(diagnostics: dict[str, float]) -> str:
        positives = sorted(diagnostics.items(), key=lambda pair: pair[1], reverse=True)[:2]
        negatives = sorted(diagnostics.items(), key=lambda pair: pair[1])[:1]
        parts = [f"{name}={value:.2f}" for name, value in positives if value > 0]
        parts.extend(f"{name}={value:.2f}" for name, value in negatives if value < 0)
        return ", ".join(parts) if parts else "neutral fund factor profile"

    @staticmethod
    def _safe_float(value: float, default: float = 0.0) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if math.isfinite(parsed) else default
