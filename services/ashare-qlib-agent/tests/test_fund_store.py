import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ashare_qlib_agent.fund_store import FundStore
from ashare_qlib_agent.fund_sync import FundDataSyncer
from ashare_qlib_agent.settings import DatabaseSettings, FundDataSettings, RuntimeSettings
from tests.fake_fund_source import FakeFundDataSource


class FundStoreTest(unittest.TestCase):
    def test_sync_can_persist_into_sqlite_store_without_csv_mirror(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            db_path = root / "funds.sqlite3"
            database = DatabaseSettings(enabled=True, url=f"sqlite:///{db_path}", schema="", mirror_csv=False)
            settings = FundDataSettings(
                benchmark_index_code="000300",
                fund_codes=["ETF001", "BOND01", "LOF001"],
            )

            report = FundDataSyncer(
                data_dir,
                settings,
                source=FakeFundDataSource(),
                database=database,
            ).sync(start_date="20260529", end_date="20260603")

            self.assertEqual(report.files, [])
            store = FundStore(database.url, schema=database.schema)
            bundle = store.load_bundle()
            status = store.status()

            self.assertEqual(len(bundle.fund_pool), 3)
            self.assertEqual(len(bundle.fund_metadata), 3)
            self.assertEqual(set(bundle.benchmark["index_code"]), {"000300"})
            self.assertTrue(status.latest_sync_at)
            self.assertFalse((data_dir / "fund_pool.csv").exists())

    def test_cycle_result_can_be_loaded_from_latest_cycle_store(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            registry_dir = root / "registry"
            db_path = root / "funds.sqlite3"
            database = DatabaseSettings(enabled=True, url=f"sqlite:///{db_path}", schema="", mirror_csv=False, save_cycles=True)
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
                database=database,
            )
            settings.ensure_dirs()
            FundDataSyncer(
                data_dir,
                settings.fund_data,
                source=FakeFundDataSource(),
                database=database,
            ).sync(start_date=settings.start_date, end_date=settings.end_date)

            from ashare_qlib_agent.fund_live_cycle import cycle_from_settings, latest_cycle_from_store

            payload = cycle_from_settings(settings)
            latest = latest_cycle_from_store(settings)

            self.assertIsNotNone(latest)
            self.assertEqual(payload["cycle_id"], latest["cycle_id"])
            self.assertTrue(latest["suggestions"])


if __name__ == "__main__":
    unittest.main()
