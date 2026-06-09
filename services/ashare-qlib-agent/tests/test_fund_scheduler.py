import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ashare_qlib_agent.fund_account_service import FundAccountService
from ashare_qlib_agent.fund_scheduler import FundTaskScheduler
from ashare_qlib_agent.fund_store import FundStore
from ashare_qlib_agent.fund_sync import FundDataSyncer
from ashare_qlib_agent.settings import DatabaseSettings, FundDataSettings, RuntimeSettings, SchedulerSettings
from tests.fake_fund_source import FakeFundDataSource


class FundSchedulerTest(unittest.TestCase):
    def test_run_once_uses_db_snapshot_and_persists_latest_cycle(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            registry_dir = root / "registry"
            db_path = root / "funds.sqlite3"
            portfolio_path = root / "portfolio.json"
            portfolio_path.write_text(
                json.dumps({"cash": 100000.0, "equity": 100000.0, "positions": []}),
                encoding="utf-8",
            )
            settings = RuntimeSettings(
                data_dir=data_dir,
                registry_dir=registry_dir,
                start_date="20260529",
                end_date="20260603",
                fund_data=FundDataSettings(
                    benchmark_index_code="000300",
                    fund_codes=["ETF001", "BOND01", "LOF001"],
                    portfolio_mode="balanced",
                    reference_date="2026-06-03",
                ),
                database=DatabaseSettings(enabled=True, url=f"sqlite:///{db_path}", schema="", mirror_csv=False, save_cycles=True),
                scheduler=SchedulerSettings(
                    enabled=False,
                    sync_before_cycle=False,
                    portfolio_file=str(portfolio_path),
                ),
            )
            settings.ensure_dirs()
            FundDataSyncer(
                data_dir,
                settings.fund_data,
                source=FakeFundDataSource(),
                database=settings.database,
            ).sync(start_date=settings.start_date, end_date=settings.end_date)

            report = FundTaskScheduler(settings).run_once()
            latest = FundStore.from_settings(settings).latest_cycle()

            self.assertIsNotNone(report.cycle)
            self.assertIsNone(report.sync)
            self.assertIsNotNone(latest)
            self.assertEqual(report.cycle["cycle_id"], latest["cycle_id"])
            self.assertTrue(latest["review"]["summary"])

    def test_run_once_uses_saved_account_when_scheduler_portfolio_is_empty(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            registry_dir = root / "registry"
            db_path = root / "funds.sqlite3"
            settings = RuntimeSettings(
                data_dir=data_dir,
                registry_dir=registry_dir,
                start_date="20260529",
                end_date="20260603",
                fund_data=FundDataSettings(
                    benchmark_index_code="000300",
                    fund_codes=["ETF001", "BOND01", "LOF001"],
                    portfolio_mode="balanced",
                    reference_date="2026-06-03",
                ),
                database=DatabaseSettings(enabled=True, url=f"sqlite:///{db_path}", schema="", mirror_csv=False, save_cycles=True),
                scheduler=SchedulerSettings(
                    enabled=False,
                    sync_before_cycle=False,
                    portfolio_file="",
                ),
            )
            settings.ensure_dirs()
            FundDataSyncer(
                data_dir,
                settings.fund_data,
                source=FakeFundDataSource(),
                database=settings.database,
            ).sync(start_date=settings.start_date, end_date=settings.end_date)
            FundAccountService.from_settings(settings).upsert_account(
                {
                    "account_id": "default",
                    "base_currency": "CNY",
                    "target_total_assets": 500_000.0,
                    "cash_balance": 500_000.0,
                }
            )

            report = FundTaskScheduler(settings).run_once()

            self.assertEqual(report.cycle["blackboard"]["portfolio_report"]["portfolio_equity"], 500_000.0)
            self.assertEqual(report.cycle["blackboard"]["portfolio_report"]["current_cash"], 500_000.0)


if __name__ == "__main__":
    unittest.main()
