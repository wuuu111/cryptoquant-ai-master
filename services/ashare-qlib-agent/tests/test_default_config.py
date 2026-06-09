import os
import unittest
from unittest.mock import patch

from app import main as fastapi_main
from ashare_qlib_agent import cli, http_server


class _DummySettings:
    def ensure_dirs(self) -> None:
        return None


class DefaultConfigTest(unittest.TestCase):
    def test_cli_defaults_to_real_local_config(self):
        captured: list[str] = []

        with patch("ashare_qlib_agent.cli.RuntimeSettings.load", side_effect=lambda path: captured.append(path) or _DummySettings()):
            with patch("ashare_qlib_agent.cli.feature_snapshot_from_settings", return_value={}):
                with patch("ashare_qlib_agent.cli.print_json"):
                    cli.main(["fund-features", "--limit", "0"])

        self.assertEqual(captured, ["config.real-local.yaml"])

    def test_fastapi_default_config_path_uses_real_local_when_env_missing(self):
        previous = os.environ.pop("FUND_AGENT_CONFIG", None)
        try:
            self.assertEqual(fastapi_main._default_config_path(), "config.real-local.yaml")
        finally:
            if previous is not None:
                os.environ["FUND_AGENT_CONFIG"] = previous

    def test_http_server_default_config_path_uses_real_local_when_env_missing(self):
        previous = os.environ.pop("FUND_AGENT_CONFIG", None)
        try:
            self.assertEqual(http_server._default_config_path(), "config.real-local.yaml")
        finally:
            if previous is not None:
                os.environ["FUND_AGENT_CONFIG"] = previous


if __name__ == "__main__":
    unittest.main()
