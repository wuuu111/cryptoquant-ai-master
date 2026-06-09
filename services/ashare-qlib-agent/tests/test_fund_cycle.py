import unittest
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from ashare_qlib_agent.schemas import PortfolioState, Position
from ashare_qlib_agent.settings import FundDataSettings, RuntimeSettings


class FundCycleTest(unittest.TestCase):
    def test_fund_cycle_from_csv_generates_rebalance_suggestions(self):
        os.environ["ASHARE_LLM_ENABLED"] = "0"
        from ashare_qlib_agent.fund_live_cycle import cycle_from_fund_csv

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            registry_dir = root / "registry"
            data_dir.mkdir()
            registry_dir.mkdir()

            pd.DataFrame(
                [
                    {
                        "fund_code": "EQ001",
                        "fund_name": "Equity Alpha",
                        "category": "equity",
                        "fund_type": "ETF",
                        "tracking_index": "CSI300",
                        "risk_level": "high",
                        "enabled": 1,
                    },
                    {
                        "fund_code": "BOND001",
                        "fund_name": "Bond Shield",
                        "category": "bond",
                        "fund_type": "LOF",
                        "tracking_index": "",
                        "risk_level": "low",
                        "enabled": 1,
                    },
                    {
                        "fund_code": "GOLD001",
                        "fund_name": "Gold Guard",
                        "category": "commodity",
                        "fund_type": "ETF",
                        "tracking_index": "AU9999",
                        "risk_level": "medium",
                        "enabled": 1,
                    },
                    {
                        "fund_code": "CASH001",
                        "fund_name": "Cash Anchor",
                        "category": "cash",
                        "fund_type": "money_market",
                        "tracking_index": "",
                        "risk_level": "low",
                        "enabled": 1,
                    },
                ]
            ).to_csv(data_dir / "fund_pool.csv", index=False)

            nav_rows = []
            dates = pd.date_range("2026-01-01", periods=140, freq="D")
            for index, date in enumerate(dates):
                nav_rows.extend(
                    [
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "fund_code": "EQ001",
                            "nav": 1.0 + index * 0.004,
                            "daily_return": 0.004,
                        },
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "fund_code": "BOND001",
                            "nav": 1.0 + index * 0.001,
                            "daily_return": 0.001,
                        },
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "fund_code": "GOLD001",
                            "nav": 1.0 + index * 0.002,
                            "daily_return": 0.002,
                        },
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "fund_code": "CASH001",
                            "nav": 1.0 + index * 0.0002,
                            "daily_return": 0.0002,
                        },
                    ]
                )
            pd.DataFrame(nav_rows).to_csv(data_dir / "fund_nav_daily.csv", index=False)

            pd.DataFrame(
                [
                    {
                        "fund_code": "EQ001",
                        "fund_name": "Equity Alpha",
                        "category": "equity",
                        "fund_type": "ETF",
                        "fee": 0.6,
                        "aum": 10_000_000,
                        "manager": "A",
                        "purchase_status": "open",
                        "redemption_status": "open",
                    },
                    {
                        "fund_code": "BOND001",
                        "fund_name": "Bond Shield",
                        "category": "bond",
                        "fund_type": "LOF",
                        "fee": 0.3,
                        "aum": 8_000_000,
                        "manager": "B",
                        "purchase_status": "open",
                        "redemption_status": "open",
                    },
                    {
                        "fund_code": "GOLD001",
                        "fund_name": "Gold Guard",
                        "category": "commodity",
                        "fund_type": "ETF",
                        "fee": 0.5,
                        "aum": 6_000_000,
                        "manager": "C",
                        "purchase_status": "open",
                        "redemption_status": "open",
                    },
                    {
                        "fund_code": "CASH001",
                        "fund_name": "Cash Anchor",
                        "category": "cash",
                        "fund_type": "money_market",
                        "fee": 0.1,
                        "aum": 20_000_000,
                        "manager": "D",
                        "purchase_status": "open",
                        "redemption_status": "open",
                    },
                ]
            ).to_csv(data_dir / "fund_metadata.csv", index=False)

            pd.DataFrame(
                [
                    {"date": day.strftime("%Y-%m-%d"), "index_code": "BENCH", "close": 1000 + offset, "daily_return": 0.002}
                    for offset, day in enumerate(dates)
                ]
            ).to_csv(data_dir / "benchmark_index.csv", index=False)

            settings = RuntimeSettings(
                data_dir=data_dir,
                registry_dir=registry_dir,
                fund_data=FundDataSettings(
                    fund_pool_file="fund_pool.csv",
                    fund_nav_file="fund_nav_daily.csv",
                fund_metadata_file="fund_metadata.csv",
                benchmark_file="benchmark_index.csv",
                portfolio_mode="balanced",
                reference_date=dates[-1].strftime("%Y-%m-%d"),
            ),
            )
            settings.ensure_dirs()

            result = cycle_from_fund_csv(
                settings,
                portfolio=PortfolioState(
                    cash=30_000.0,
                    equity=100_000.0,
                    positions=[
                        Position(
                            symbol="BOND001",
                            shares=0,
                            available_shares=0,
                            market_value=20_000.0,
                            weight=0.20,
                            category="bond",
                        )
                    ],
                ),
            )

            self.assertEqual(result["market"]["gate"], "ALLOW_FULL")
            self.assertTrue(result["scores"])
            self.assertTrue(result["targets"])
            self.assertTrue(result["suggestions"])
            self.assertEqual(result["orders"], [])
            self.assertGreaterEqual(result["review"]["metrics"]["suggestions"], 1)
            self.assertIn("market_report", result["blackboard"])
            self.assertIn("risk_report", result["blackboard"])
            self.assertTrue(result["agent_trace"])
            self.assertTrue(result["collaboration_events"])

    def test_fund_cycle_uses_initial_cash_when_portfolio_is_omitted(self):
        os.environ["ASHARE_LLM_ENABLED"] = "0"
        from ashare_qlib_agent.fund_live_cycle import cycle_from_fund_csv

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            registry_dir = root / "registry"
            data_dir.mkdir()
            registry_dir.mkdir()

            pd.DataFrame(
                [
                    {
                        "fund_code": "EQ001",
                        "fund_name": "Equity Alpha",
                        "category": "equity",
                        "fund_type": "ETF",
                        "tracking_index": "CSI300",
                        "risk_level": "high",
                        "enabled": 1,
                    },
                    {
                        "fund_code": "BOND001",
                        "fund_name": "Bond Shield",
                        "category": "bond",
                        "fund_type": "LOF",
                        "tracking_index": "",
                        "risk_level": "low",
                        "enabled": 1,
                    },
                    {
                        "fund_code": "GOLD001",
                        "fund_name": "Gold Guard",
                        "category": "commodity",
                        "fund_type": "ETF",
                        "tracking_index": "AU9999",
                        "risk_level": "medium",
                        "enabled": 1,
                    },
                    {
                        "fund_code": "CASH001",
                        "fund_name": "Cash Anchor",
                        "category": "cash",
                        "fund_type": "money_market",
                        "tracking_index": "",
                        "risk_level": "low",
                        "enabled": 1,
                    },
                ]
            ).to_csv(data_dir / "fund_pool.csv", index=False)

            nav_rows = []
            dates = pd.date_range("2026-01-01", periods=140, freq="D")
            for index, date in enumerate(dates):
                nav_rows.extend(
                    [
                        {"date": date.strftime("%Y-%m-%d"), "fund_code": "EQ001", "nav": 1.0 + index * 0.004, "daily_return": 0.004},
                        {"date": date.strftime("%Y-%m-%d"), "fund_code": "BOND001", "nav": 1.0 + index * 0.001, "daily_return": 0.001},
                        {"date": date.strftime("%Y-%m-%d"), "fund_code": "GOLD001", "nav": 1.0 + index * 0.002, "daily_return": 0.002},
                        {"date": date.strftime("%Y-%m-%d"), "fund_code": "CASH001", "nav": 1.0 + index * 0.0002, "daily_return": 0.0002},
                    ]
                )
            pd.DataFrame(nav_rows).to_csv(data_dir / "fund_nav_daily.csv", index=False)

            pd.DataFrame(
                [
                    {"fund_code": "EQ001", "fund_name": "Equity Alpha", "category": "equity", "fund_type": "ETF", "fee": 0.6, "aum": 10_000_000, "manager": "A", "purchase_status": "open", "redemption_status": "open"},
                    {"fund_code": "BOND001", "fund_name": "Bond Shield", "category": "bond", "fund_type": "LOF", "fee": 0.3, "aum": 8_000_000, "manager": "B", "purchase_status": "open", "redemption_status": "open"},
                    {"fund_code": "GOLD001", "fund_name": "Gold Guard", "category": "commodity", "fund_type": "ETF", "fee": 0.5, "aum": 6_000_000, "manager": "C", "purchase_status": "open", "redemption_status": "open"},
                    {"fund_code": "CASH001", "fund_name": "Cash Anchor", "category": "cash", "fund_type": "money_market", "fee": 0.1, "aum": 20_000_000, "manager": "D", "purchase_status": "open", "redemption_status": "open"},
                ]
            ).to_csv(data_dir / "fund_metadata.csv", index=False)

            pd.DataFrame(
                [{"date": day.strftime("%Y-%m-%d"), "index_code": "BENCH", "close": 1000 + offset, "daily_return": 0.002} for offset, day in enumerate(dates)]
            ).to_csv(data_dir / "benchmark_index.csv", index=False)

            settings = RuntimeSettings(
                data_dir=data_dir,
                registry_dir=registry_dir,
                portfolio=RuntimeSettings().portfolio,
                fund_data=FundDataSettings(
                    fund_pool_file="fund_pool.csv",
                    fund_nav_file="fund_nav_daily.csv",
                    fund_metadata_file="fund_metadata.csv",
                    benchmark_file="benchmark_index.csv",
                    portfolio_mode="balanced",
                    reference_date=dates[-1].strftime("%Y-%m-%d"),
                ),
            )
            settings.ensure_dirs()

            result = cycle_from_fund_csv(settings)

            self.assertTrue(result["targets"])
            self.assertTrue(result["suggestions"])


if __name__ == "__main__":
    unittest.main()
