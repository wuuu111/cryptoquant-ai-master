import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.main import app
from ashare_qlib_agent.fund_live_cycle import cycle_from_settings, latest_cycle_from_store
from ashare_qlib_agent.schemas import PortfolioState, Position
from ashare_qlib_agent.fund_sync import FundDataSyncer
from ashare_qlib_agent.settings import RuntimeSettings
from tests.fake_fund_source import FakeFundDataSource


def _write_config(root: Path) -> Path:
    config_path = root / "config.yaml"
    db_path = root / "funds.sqlite3"
    config_path.write_text(
        "\n".join(
            [
                f"data_dir: {root / 'data'}",
                f"registry_dir: {root / 'registry'}",
                "start_date: '20260529'",
                "end_date: '20260603'",
                "portfolio:",
                "  initial_cash: 1000000",
                "fund_data:",
                "  benchmark_index_code: '000300'",
                "  portfolio_mode: 'balanced'",
                "  reference_date: '2026-06-03'",
                "  fund_codes: ['ETF001', 'BOND01', 'LOF001']",
                "database:",
                "  enabled: true",
                f"  url: 'sqlite:///{db_path}'",
                "  schema: ''",
                "  mirror_csv: false",
                "  save_cycles: true",
                "scheduler:",
                "  enabled: false",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


class FundAccountApiTest(unittest.TestCase):
    def test_account_endpoints_round_trip(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_config(root)
            os.environ["FUND_AGENT_CONFIG"] = str(config_path)
            with TestClient(app) as client:
                create = client.post(
                    "/account",
                    json={
                        "account_id": "default",
                        "base_currency": "CNY",
                        "target_total_assets": 1_000_000,
                        "cash_balance": 1_000_000,
                    },
                )
                self.assertEqual(create.status_code, 200)

                read_back = client.get("/account")
                self.assertEqual(read_back.status_code, 200)
                self.assertEqual(read_back.json()["target_total_assets"], 1_000_000)

    def test_apply_suggestion_creates_trade_and_changes_positions(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_config(root)
            os.environ["FUND_AGENT_CONFIG"] = str(config_path)
            settings = RuntimeSettings.load(config_path)
            settings.ensure_dirs()
            FundDataSyncer(
                settings.data_dir,
                settings.fund_data,
                source=FakeFundDataSource(),
                database=settings.database,
            ).sync(start_date=settings.start_date, end_date=settings.end_date)
            cycle_from_settings(
                settings,
                portfolio=PortfolioState(
                    cash=200_000.0,
                    equity=1_000_000.0,
                    positions=[
                        Position(
                            symbol="LEGACY1",
                            shares=1000,
                            available_shares=1000,
                            market_value=120_000.0,
                            cost_basis=1.2,
                            category="equity",
                            fund_type="ETF",
                            weight=0.12,
                        )
                    ],
                ),
            )
            latest = latest_cycle_from_store(settings) or {}
            suggestion = next(item for item in latest.get("suggestions", []) if not item.get("blocked"))

            with TestClient(app) as client:
                response = client.post(
                    f"/suggestions/{suggestion['suggestion_id']}/apply",
                    json={"account_id": "default", "executed_price": 1.0},
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["trade"]["source"], "suggestion_apply")
                self.assertTrue(payload["trade"]["fund_name"])
                if payload["trade"]["side"] == "BUY":
                    self.assertLess(payload["account"]["cash_balance"], payload["account"]["target_total_assets"])
                else:
                    self.assertGreater(payload["account"]["cash_balance"], payload["account"]["target_total_assets"])
                self.assertIn("positions", payload)
                trades_payload = client.get("/trades").json()
                self.assertEqual(trades_payload["count"], 1)


if __name__ == "__main__":
    unittest.main()
