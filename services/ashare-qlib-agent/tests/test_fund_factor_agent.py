import unittest

from ashare_qlib_agent.fund_factor_agent import FundFactorAgent
from ashare_qlib_agent.schemas import InstrumentFeature


class FundFactorAgentTest(unittest.TestCase):
    def test_scores_rank_stronger_equity_fund_above_weaker_bond_fund(self):
        agent = FundFactorAgent()
        scores = agent.score(
            [
                InstrumentFeature(
                    symbol="EQ001",
                    close=1.5,
                    category="equity",
                    factors={
                        "return_5d": 0.03,
                        "return_20d": 0.12,
                        "return_60d": 0.24,
                        "return_120d": 0.42,
                        "volatility_60d": 0.02,
                        "max_drawdown_60d": -0.04,
                        "max_drawdown_120d": -0.08,
                        "ma20": 1.40,
                        "ma60": 1.30,
                        "distance_to_60d_high": -0.01,
                    },
                ),
                InstrumentFeature(
                    symbol="BOND001",
                    close=1.1,
                    category="bond",
                    factors={
                        "return_5d": 0.002,
                        "return_20d": 0.01,
                        "return_60d": 0.03,
                        "return_120d": 0.05,
                        "volatility_60d": 0.01,
                        "max_drawdown_60d": -0.01,
                        "max_drawdown_120d": -0.02,
                        "ma20": 1.09,
                        "ma60": 1.08,
                        "distance_to_60d_high": -0.03,
                    },
                ),
            ],
            market_regime="BULL_TREND",
        )

        self.assertEqual(scores[0].symbol, "EQ001")
        self.assertEqual(scores[0].rank, 1)
        self.assertGreater(scores[0].combined_score, scores[1].combined_score)

    def test_short_history_inputs_do_not_crash_factor_scoring(self):
        agent = FundFactorAgent()
        scores = agent.score(
            [
                InstrumentFeature(
                    symbol="EQ001",
                    close=1.0,
                    category="equity",
                    factors={
                        "return_5d": float("nan"),
                        "return_20d": float("nan"),
                        "return_60d": float("nan"),
                        "return_120d": float("nan"),
                        "volatility_60d": float("nan"),
                        "max_drawdown_60d": float("nan"),
                        "max_drawdown_120d": float("nan"),
                        "ma20": float("nan"),
                        "ma60": float("nan"),
                        "distance_to_60d_high": float("nan"),
                    },
                ),
                InstrumentFeature(
                    symbol="BOND001",
                    close=1.0,
                    category="bond",
                    factors={
                        "return_5d": float("nan"),
                        "return_20d": float("nan"),
                        "return_60d": float("nan"),
                        "return_120d": float("nan"),
                        "volatility_60d": float("nan"),
                        "max_drawdown_60d": float("nan"),
                        "max_drawdown_120d": float("nan"),
                        "ma20": float("nan"),
                        "ma60": float("nan"),
                        "distance_to_60d_high": float("nan"),
                    },
                ),
            ],
            market_regime="RANGE",
        )

        self.assertEqual(len(scores), 2)


if __name__ == "__main__":
    unittest.main()
