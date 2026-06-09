import unittest

from ashare_qlib_agent.fund_execution_agent import FundExecutionAgent
from ashare_qlib_agent.fund_portfolio_agent import FundPortfolioAgent
from ashare_qlib_agent.fund_risk_agent import FundRiskAgent
from ashare_qlib_agent.schemas import FactorScore, InstrumentFeature, MarketRegimeResult, PortfolioState, Position, TargetPosition


class FundPortfolioRiskTest(unittest.TestCase):
    def test_balanced_mode_respects_bucket_targets(self):
        portfolio_agent = FundPortfolioAgent()
        market = MarketRegimeResult(
            regime="BULL_TREND",
            gate="ALLOW_FULL",
            score=0.2,
            reason="supportive",
            exposure_multiplier=1.0,
        )
        portfolio = PortfolioState(cash=20_000.0, equity=100_000.0)
        scores = [
            FactorScore("EQ001", "equity", 1.2, 1.0, None, 1.0, 1),
            FactorScore("EQ002", "equity", 1.1, 0.9, None, 0.9, 2),
            FactorScore("BOND001", "bond", 1.0, 0.6, None, 0.6, 3),
            FactorScore("GOLD001", "commodity", 1.0, 0.5, None, 0.5, 4),
            FactorScore("CASH001", "cash", 1.0, 0.2, None, 0.2, 5),
        ]

        _, targets = portfolio_agent.build_targets(scores, market, portfolio, mode="balanced")
        weight_by_symbol = {item.symbol: item.target_weight for item in targets}

        self.assertAlmostEqual(weight_by_symbol["BOND001"], 0.20, places=6)
        self.assertAlmostEqual(weight_by_symbol["GOLD001"], 0.10, places=6)
        self.assertAlmostEqual(weight_by_symbol["CASH001"], 0.05, places=6)
        self.assertAlmostEqual(weight_by_symbol["EQ001"], 0.20, places=6)
        self.assertAlmostEqual(weight_by_symbol["EQ002"], 0.20, places=6)

    def test_risk_agent_blocks_purchase_closed_fund(self):
        portfolio_agent = FundPortfolioAgent()
        risk_agent = FundRiskAgent()
        execution_agent = FundExecutionAgent()
        market = MarketRegimeResult(
            regime="RANGE",
            gate="ALLOW_FULL",
            score=0.05,
            reason="neutral",
            exposure_multiplier=0.85,
        )
        portfolio = PortfolioState(
            cash=30_000.0,
            equity=100_000.0,
            positions=[Position(symbol="BOND001", shares=0, available_shares=0, market_value=15_000.0, weight=0.15, category="bond")],
        )
        scores = [
            FactorScore("EQ001", "equity", 1.2, 1.0, None, 1.0, 1),
            FactorScore("BOND001", "bond", 1.0, 0.6, None, 0.6, 2),
            FactorScore("GOLD001", "commodity", 1.0, 0.5, None, 0.5, 3),
            FactorScore("CASH001", "cash", 1.0, 0.2, None, 0.2, 4),
        ]
        signals, targets = portfolio_agent.build_targets(scores, market, portfolio, mode="balanced")
        instruments = [
            InstrumentFeature(symbol="EQ001", close=1.2, category="equity", purchase_status="closed", redemption_status="open"),
            InstrumentFeature(symbol="BOND001", close=1.0, category="bond", purchase_status="open", redemption_status="open"),
            InstrumentFeature(symbol="GOLD001", close=1.0, category="commodity", purchase_status="open", redemption_status="open"),
            InstrumentFeature(symbol="CASH001", close=1.0, category="cash", purchase_status="open", redemption_status="open"),
        ]

        adjusted_signals, allowed_targets, blocked_suggestions, reasons = risk_agent.filter_targets(
            targets,
            signals,
            market,
            instruments,
            portfolio,
        )
        suggestions = execution_agent.build_suggestions(allowed_targets, portfolio, blocked_suggestions=blocked_suggestions)

        self.assertTrue(any(item.symbol == "EQ001" and item.action == "HOLD" for item in adjusted_signals))
        self.assertFalse(any(item.symbol == "EQ001" for item in allowed_targets))
        self.assertTrue(reasons)
        self.assertTrue(any(item.symbol == "EQ001" and item.blocked for item in suggestions))

    def test_reduced_risk_regime_scales_total_target_exposure(self):
        portfolio_agent = FundPortfolioAgent()
        market = MarketRegimeResult(
            regime="BEAR_TREND",
            gate="ALLOW_REDUCED",
            score=-0.1,
            reason="reduced",
            exposure_multiplier=0.60,
        )
        portfolio = PortfolioState(cash=20_000.0, equity=100_000.0)
        scores = [
            FactorScore("EQ001", "equity", 1.2, 1.0, None, 1.0, 1),
            FactorScore("EQ002", "equity", 1.1, 0.9, None, 0.9, 2),
            FactorScore("BOND001", "bond", 1.0, 0.6, None, 0.6, 3),
            FactorScore("GOLD001", "commodity", 1.0, 0.5, None, 0.5, 4),
            FactorScore("CASH001", "cash", 1.0, 0.2, None, 0.2, 5),
        ]

        _, targets = portfolio_agent.build_targets(scores, market, portfolio, mode="balanced")

        self.assertLessEqual(sum(item.target_weight for item in targets), 0.60 + 1e-9)

    def test_execution_agent_emits_exit_suggestion_for_position_removed_from_targets(self):
        execution_agent = FundExecutionAgent()
        portfolio = PortfolioState(
            cash=0.0,
            equity=100_000.0,
            positions=[Position(symbol="OLD1", shares=0, available_shares=0, market_value=30_000.0, weight=0.30, category="bond")],
        )
        suggestions = execution_agent.build_suggestions(
            [TargetPosition(symbol="NEW1", target_weight=0.20, target_value=20_000.0, reason="new target")],
            portfolio,
        )

        self.assertTrue(any(item.symbol == "NEW1" and item.action == "INCREASE" for item in suggestions))
        self.assertTrue(any(item.symbol == "OLD1" and item.action == "DECREASE" for item in suggestions))


if __name__ == "__main__":
    unittest.main()
