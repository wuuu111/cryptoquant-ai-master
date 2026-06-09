from __future__ import annotations

from .schemas import PortfolioState, RebalanceAction, RebalanceSuggestion, TargetPosition


class FundExecutionAgent:
    def build_suggestions(
        self,
        targets: list[TargetPosition],
        portfolio: PortfolioState,
        blocked_suggestions: list[RebalanceSuggestion] | None = None,
    ) -> list[RebalanceSuggestion]:
        current_positions = {item.symbol: item for item in portfolio.positions}
        target_by_symbol = {item.symbol: item for item in targets}
        suggestions: list[RebalanceSuggestion] = []
        for target in targets:
            current_position = current_positions.get(target.symbol)
            current_value = current_position.market_value if current_position else 0.0
            current_weight = current_position.weight if current_position else 0.0
            delta_value = target.target_value - current_value
            delta_weight = target.target_weight - current_weight
            if abs(delta_value) <= 1e-6 and abs(delta_weight) <= 1e-6:
                action: RebalanceAction = "HOLD"
            elif delta_value > 0:
                action = "INCREASE"
            else:
                action = "DECREASE"
            suggestions.append(
                RebalanceSuggestion(
                    symbol=target.symbol,
                    action=action,
                    current_weight=current_weight,
                    target_weight=target.target_weight,
                    delta_weight=delta_weight,
                    current_value=current_value,
                    target_value=target.target_value,
                    delta_value=delta_value,
                    reason=target.reason,
                    blocked=False,
                )
            )
        for symbol, position in current_positions.items():
            if symbol in target_by_symbol:
                continue
            suggestions.append(
                RebalanceSuggestion(
                    symbol=symbol,
                    action="DECREASE",
                    current_weight=position.weight,
                    target_weight=0.0,
                    delta_weight=-position.weight,
                    current_value=position.market_value,
                    target_value=0.0,
                    delta_value=-position.market_value,
                    reason="Position removed from target allocation.",
                    blocked=False,
                )
            )
        suggestions.extend(blocked_suggestions or [])
        return suggestions
