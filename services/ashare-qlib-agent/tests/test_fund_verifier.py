import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ashare_qlib_agent.fund_verifier import verify_postgres
from ashare_qlib_agent.settings import DatabaseSettings, FundDataSettings, RuntimeSettings
from tests.fake_fund_source import FakeFundDataSource


class FundVerifierTest(unittest.TestCase):
    def test_verify_postgres_runs_against_sqlite(self):
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
                    url=f"sqlite:///{root / 'verify.sqlite3'}",
                    schema="",
                    mirror_csv=False,
                    save_cycles=True,
                ),
            )
            settings.ensure_dirs()

            payload = verify_postgres(
                settings,
                source=FakeFundDataSource(),
            )

            self.assertEqual(payload["sync_report"]["fund_count"], 3)
            self.assertEqual(payload["row_counts"]["fund_pool"], 3)
            self.assertEqual(payload["row_counts"]["fund_cycle_runs"], 1)
            self.assertTrue(payload["cycle"]["cycle_id"])
            self.assertEqual(payload["latest_cycle_id"], payload["cycle"]["cycle_id"])


if __name__ == "__main__":
    unittest.main()
