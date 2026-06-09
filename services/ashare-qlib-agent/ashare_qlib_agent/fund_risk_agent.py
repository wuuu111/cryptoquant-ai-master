from __future__ import annotations

from .schemas import (
    InstrumentFeature,
    MarketRegimeResult,
    PortfolioState,
    RebalanceAction,
    RebalanceSuggestion,
    Signal,
    TargetPosition,
)


class FundRiskAgent:
    def filter_targets(
        self,
        targets: list[TargetPosition],
        signals: list[Signal],
        market: MarketRegimeResult,
        instruments: list[InstrumentFeature],
        portfolio: PortfolioState,
        min_defensive_weight: float = 0.10,
        max_turnover: float = 0.30,
    ) -> tuple[list[Signal], list[TargetPosition], list[RebalanceSuggestion], list[str]]:
        by_symbol = {item.symbol: item for item in instruments}
        current_positions = {item.symbol: item for item in portfolio.positions}
        allowed_targets: list[TargetPosition] = []
        adjusted_signals: list[Signal] = []
        blocked_suggestions: list[RebalanceSuggestion] = []
        reasons: list[str] = []

        for signal in signals:
            instrument = by_symbol.get(signal.symbol)
            if instrument is None:
                continue
            current_position = current_positions.get(signal.symbol)
            current_weight = current_position.weight if current_position else 0.0
            current_value = current_position.market_value if current_position else 0.0
            delta_weight = signal.target_weight - current_weight
            intended_action: RebalanceAction = (
                "INCREASE" if delta_weight > 1e-9 else "DECREASE" if delta_weight < -1e-9 else "HOLD"
            )
            block_reason = None
            if not instrument.enabled:
                block_reason = "Fund disabled."
            elif instrument.stale:
                block_reason = "Fund NAV is stale."
            elif delta_weight > 1e-9 and instrument.purchase_status.lower() != "open":
                block_reason = "Purchase status is closed."
            elif delta_weight < -1e-9 and instrument.redemption_status.lower() != "open":
                block_reason = "Redemption status is closed."
            if signal.target_weight > 0 and instrument.category.lower() == "qdii" and signal.target_weight > 0.20:
                block_reason = "QDII cap exceeded."
            if signal.target_weight > 0 and instrument.category.lower() == "commodity" and signal.target_weight > 0.15:
                block_reason = "Commodity cap exceeded."

            if block_reason:
                adjusted_signals.append(
                    Signal(
                        symbol=signal.symbol,
                        action="HOLD",
                        confidence=0.0,
                        target_weight=0.0,
                        score=signal.score,
                        reason=block_reason,
                    )
                )
                reasons.append(block_reason)
                blocked_suggestions.append(
                    RebalanceSuggestion(
                        symbol=signal.symbol,
                        action=intended_action,
                        current_weight=current_weight,
                        target_weight=signal.target_weight,
                        delta_weight=delta_weight,
                        current_value=current_value,
                        target_value=portfolio.equity * signal.target_weight,
                        delta_value=(portfolio.equity * signal.target_weight) - current_value,
                        reason=block_reason,
                        blocked=True,
                    )
                )
                continue

            adjusted_signals.append(signal)
            matched_target = next((item for item in targets if item.symbol == signal.symbol), None)
            if matched_target is not None:
                allowed_targets.append(matched_target)

        defensive_weight = sum(
            item.target_weight for item in allowed_targets if by_symbol[item.symbol].category.lower() in {"bond", "cash"}
        )
        if defensive_weight < min_defensive_weight:
            reasons.append("Minimum bond or cash allocation violated.")

        target_weight_by_symbol = {item.symbol: item.target_weight for item in allowed_targets}
        all_symbols = set(target_weight_by_symbol) | set(current_positions)
        current_total_weight = sum(item.weight for item in current_positions.values())
        turnover = sum(
            abs(target_weight_by_symbol.get(symbol, 0.0) - position.weight)
            for symbol in all_symbols
            for position in [current_positions.get(symbol)]
            if position is not None
        )
        turnover += sum(
            abs(target_weight_by_symbol.get(symbol, 0.0))
            for symbol in all_symbols
            if current_positions.get(symbol) is None
        )
        if market.gate == "ALLOW_FULL" and current_total_weight >= 0.50 and turnover > max_turnover:
            reasons.append("Turnover cap violated.")
            for item in allowed_targets:
                current_position = current_positions.get(item.symbol)
                current_weight = current_position.weight if current_position else 0.0
                current_value = current_position.market_value if current_position else 0.0
                delta_weight = item.target_weight - current_weight
                blocked_action: RebalanceAction = (
                    "INCREASE" if delta_weight > 0 else "DECREASE" if delta_weight < 0 else "HOLD"
                )
                blocked_suggestions.append(
                    RebalanceSuggestion(
                        symbol=item.symbol,
                        action=blocked_action,
                        current_weight=current_weight,
                        target_weight=item.target_weight,
                        delta_weight=delta_weight,
                        current_value=current_value,
                        target_value=item.target_value,
                        delta_value=item.target_value - current_value,
                        reason="Turnover cap violated.",
                        blocked=True,
                    )
                )
            allowed_targets = []
            adjusted_signals = [
                Signal(
                    symbol=item.symbol,
                    action="HOLD",
                    confidence=0.0,
                    target_weight=0.0,
                    score=item.score,
                    reason="Turnover cap violated.",
                )
                if item.target_weight > 0
                else item
                for item in adjusted_signals
            ]

        return adjusted_signals, allowed_targets, blocked_suggestions, reasons
