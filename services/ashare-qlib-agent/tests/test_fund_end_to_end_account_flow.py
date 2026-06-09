import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ashare_qlib_agent.fund_account_service import FundAccountService
from ashare_qlib_agent.fund_scheduler import FundTaskScheduler
from ashare_qlib_agent.fund_sync import FundDataSyncer
from ashare_qlib_agent.settings import (
    AccountSettings,
    DatabaseSettings,
    FundDataSettings,
    FundGraphSettings,
    RuntimeSettings,
    SchedulerSettings,
)
from tests.fake_fund_source import FakeFundDataSource


class FundEndToEndAccountFlowTest(unittest.TestCase):
    def test_scheduler_cycle_and_manual_trade_update_same_account(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = RuntimeSettings(
                data_dir=root / "data",
                registry_dir=root / "registry",
                start_date="20260529",
                end_date="20260603",
                fund_data=FundDataSettings(
                    benchmark_index_code="000300",
                    fund_codes=["ETF001", "BOND01", "LOF001"],
                    portfolio_mode="balanced",
                    reference_date="2026-06-03",
                ),
                database=DatabaseSettings(
                    enabled=True,
                    url=f"sqlite:///{root / 'funds.sqlite3'}",
                    schema="",
                    mirror_csv=False,
                    save_cycles=True,
                ),
                account=AccountSettings(default_account_id="household", base_currency="CNY"),
                fund_graph=FundGraphSettings(enabled=True, llm_enabled=False),
                scheduler=SchedulerSettings(
                    enabled=False,
                    sync_before_cycle=False,
                    portfolio_file="",
                ),
            )
            settings.ensure_dirs()
            FundDataSyncer(
                settings.data_dir,
                settings.fund_data,
                source=FakeFundDataSource(),
                database=settings.database,
            ).sync(start_date=settings.start_date, end_date=settings.end_date)

            service = FundAccountService.from_settings(settings)
            service.upsert_account(
                {
                    "account_id": "household",
                    "base_currency": "CNY",
                    "target_total_assets": 300_000.0,
                    "cash_balance": 300_000.0,
                }
            )

            scheduler = FundTaskScheduler(settings, account_id="household")
            first = scheduler.run_once()
            self.assertTrue(first.cycle["suggestions"])
            self.assertEqual(first.cycle["blackboard"]["portfolio_report"]["portfolio_equity"], 300_000.0)
            self.assertEqual(first.cycle["blackboard"]["portfolio_report"]["current_cash"], 300_000.0)

            trade = service.create_manual_trade(
                {
                    "symbol": "ETF001",
                    "fund_name": "Equity Alpha ETF",
                    "side": "BUY",
                    "amount": 10_000.0,
                    "price": 1.0,
                },
                account_id="household",
            )
            account = service.get_account(account_id="household")
            positions = service.list_positions(account_id="household")

            self.assertEqual(trade["trade"]["source"], "manual")
            self.assertLess(account["cash_balance"], account["target_total_assets"])
            self.assertTrue(any(item["symbol"] == "ETF001" for item in positions["items"]))

            second = scheduler.run_once()
            self.assertEqual(second.cycle["blackboard"]["portfolio_report"]["portfolio_equity"], 300_000.0)
            self.assertEqual(second.cycle["blackboard"]["portfolio_report"]["current_cash"], 290_000.0)


if __name__ == "__main__":
    unittest.main()
