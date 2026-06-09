import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from ashare_qlib_agent.fund_sync import FundDataSyncer, _category_from_type
from ashare_qlib_agent.settings import FundDataSettings
from tests.fake_fund_source import FakeFundDataSource


class FundSyncTest(unittest.TestCase):
    def test_category_from_type_handles_real_fund_edge_cases(self):
        self.assertEqual(_category_from_type("指数型-固收", "国债ETF国泰"), "bond")
        self.assertEqual(_category_from_type("指数型-其他", "黄金ETF华安"), "commodity")
        self.assertEqual(_category_from_type("指数型-海外股票", "纳指ETF国泰"), "qdii")

    def test_sync_writes_four_fund_csv_files(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            settings = FundDataSettings(
                benchmark_index_code="000300",
                fund_codes=["ETF001", "BOND01", "LOF001"],
            )
            report = FundDataSyncer(data_dir, settings, source=FakeFundDataSource()).sync(
                start_date="20260529",
                end_date="20260603",
            )

            self.assertEqual(report.fund_count, 3)
            self.assertEqual(report.benchmark_rows, 3)
            self.assertEqual(report.as_of, "2026-06-03")
            self.assertEqual(len(report.files), 4)

            pool = pd.read_csv(data_dir / "fund_pool.csv")
            metadata = pd.read_csv(data_dir / "fund_metadata.csv")
            nav = pd.read_csv(data_dir / "fund_nav_daily.csv")
            benchmark = pd.read_csv(data_dir / "benchmark_index.csv")

            self.assertEqual(set(pool["fund_code"]), {"ETF001", "BOND01", "LOF001"})
            self.assertEqual(set(metadata["fund_code"]), {"ETF001", "BOND01", "LOF001"})
            self.assertEqual(set(nav["fund_code"]), {"ETF001", "BOND01", "LOF001"})
            self.assertEqual(set(pool["category"]), {"equity", "bond"})
            self.assertEqual(str(metadata.loc[metadata["fund_code"] == "LOF001", "purchase_status"].iloc[0]), "暂停申购")
            self.assertEqual(set(benchmark["index_code"].astype(str).str.zfill(6)), {"000300"})


if __name__ == "__main__":
    unittest.main()
