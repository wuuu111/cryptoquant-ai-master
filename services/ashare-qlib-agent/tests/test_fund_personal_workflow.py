import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ashare_qlib_agent.fund_fixtures import write_sample_fund_data
from ashare_qlib_agent.fund_live_cycle import cycle_from_fund_csv, feature_snapshot_from_fund_csv
from ashare_qlib_agent.settings import RuntimeSettings


class FundPersonalWorkflowTest(unittest.TestCase):
    def test_sample_fund_data_supports_feature_preview_and_cycle(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            registry_dir = root / "registry"
            sample_report = write_sample_fund_data(data_dir, periods=160, end_date="2026-06-03")

            settings = RuntimeSettings(data_dir=data_dir, registry_dir=registry_dir)
            settings.ensure_dirs()

            feature_snapshot = feature_snapshot_from_fund_csv(settings, limit=3)
            cycle_result = cycle_from_fund_csv(settings)

            self.assertEqual(sample_report["fund_count"], 6)
            self.assertEqual(feature_snapshot["as_of"], "2026-06-03")
            self.assertEqual(feature_snapshot["count"], 6)
            self.assertEqual(len(feature_snapshot["items"]), 3)
            self.assertIn("fund_code", feature_snapshot["items"][0])
            self.assertTrue(cycle_result["scores"])
            self.assertTrue(cycle_result["targets"])
            self.assertTrue(cycle_result["suggestions"])
            self.assertEqual(cycle_result["orders"], [])


if __name__ == "__main__":
    unittest.main()
