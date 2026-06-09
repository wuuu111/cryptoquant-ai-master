import os
import unittest

from ashare_qlib_agent.fund_graph_agent import FundGraphWorkflow
from ashare_qlib_agent.schemas import InstrumentFeature, MarketSnapshot, PortfolioState


def _snapshot(*, closed_purchase: bool = False) -> MarketSnapshot:
    return MarketSnapshot(
        as_of="2026-06-03",
        benchmark_returns={"000300": -0.0026},
        breadth={"advance_ratio": 0.5, "limit_up_count": 0.0, "limit_down_count": 0.0, "turnover_ratio": 1.0},
        instruments=[
            InstrumentFeature(
                symbol="ETF001",
                close=2.05,
                category="equity",
                industry="equity",
                fund_type="ETF",
                purchase_status="closed" if closed_purchase else "open",
                redemption_status="open",
                data_as_of="2026-06-03",
                factors={
                    "return_5d": 0.03,
                    "return_20d": 0.08,
                    "return_60d": 0.12,
                    "return_120d": 0.20,
                    "volatility_60d": 0.08,
                    "max_drawdown_60d": -0.05,
                    "max_drawdown_120d": -0.08,
                    "ma20": 1.98,
                    "ma60": 1.86,
                    "distance_to_60d_high": -0.02,
                },
            ),
            InstrumentFeature(
                symbol="BOND01",
                close=1.03,
                category="bond",
                industry="bond",
                fund_type="LOF",
                purchase_status="open",
                redemption_status="open",
                data_as_of="2026-06-03",
                factors={
                    "return_5d": 0.01,
                    "return_20d": 0.03,
                    "return_60d": 0.05,
                    "return_120d": 0.08,
                    "volatility_60d": 0.02,
                    "max_drawdown_60d": -0.01,
                    "max_drawdown_120d": -0.02,
                    "ma20": 1.02,
                    "ma60": 1.01,
                    "distance_to_60d_high": -0.01,
                },
            ),
            InstrumentFeature(
                symbol="GOLD01",
                close=1.20,
                category="commodity",
                industry="commodity",
                fund_type="ETF",
                purchase_status="open",
                redemption_status="open",
                data_as_of="2026-06-03",
                factors={
                    "return_5d": 0.015,
                    "return_20d": 0.04,
                    "return_60d": 0.06,
                    "return_120d": 0.09,
                    "volatility_60d": 0.04,
                    "max_drawdown_60d": -0.03,
                    "max_drawdown_120d": -0.05,
                    "ma20": 1.18,
                    "ma60": 1.15,
                    "distance_to_60d_high": -0.03,
                },
            ),
            InstrumentFeature(
                symbol="CASH01",
                close=1.00,
                category="cash",
                industry="cash",
                fund_type="money_market",
                purchase_status="open",
                redemption_status="open",
                data_as_of="2026-06-03",
                factors={
                    "return_5d": 0.001,
                    "return_20d": 0.003,
                    "return_60d": 0.006,
                    "return_120d": 0.01,
                    "volatility_60d": 0.001,
                    "max_drawdown_60d": 0.0,
                    "max_drawdown_120d": 0.0,
                    "ma20": 1.0,
                    "ma60": 1.0,
                    "distance_to_60d_high": 0.0,
                },
            ),
        ],
    )


class FundGraphWorkflowTest(unittest.TestCase):
    def test_fund_graph_workflow_returns_agent_trace_and_supervisor_summary(self):
        os.environ["ASHARE_LLM_ENABLED"] = "0"
        workflow = FundGraphWorkflow(portfolio_mode="balanced")
        result = workflow.run_cycle(
            _snapshot(),
            PortfolioState(cash=200_000.0, equity=1_000_000.0, positions=[]),
        )

        self.assertEqual(result.workflow, "fund-graph")
        self.assertTrue(any(step.name == "FundSupervisorAgent" for step in result.agent_trace))
        self.assertTrue(result.review.summary)
        self.assertIn(result.blackboard["supervisor_decision"]["decision"], {"approve", "reduce", "pause", "reject", "request_revision"})

    def test_blocked_suggestion_survives_llm_review(self):
        os.environ["ASHARE_LLM_ENABLED"] = "0"
        workflow = FundGraphWorkflow(portfolio_mode="balanced")
        result = workflow.run_cycle(
            _snapshot(closed_purchase=True),
            PortfolioState(cash=200_000.0, equity=1_000_000.0, positions=[]),
        )

        blocked = [item for item in result.suggestions if item.blocked]
        self.assertTrue(blocked)
        self.assertTrue(any("closed" in item.reason.lower() for item in blocked))


if __name__ == "__main__":
    unittest.main()
