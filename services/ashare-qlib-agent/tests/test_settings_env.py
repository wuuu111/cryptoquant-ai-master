import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ashare_qlib_agent.llm import LLMClient
from ashare_qlib_agent.settings import RuntimeSettings


class SettingsEnvTest(unittest.TestCase):
    def test_real_local_config_keeps_llm_enabled(self):
        config_path = Path(__file__).resolve().parents[1] / "config.real-local.yaml"
        previous_api_key = os.environ.get("ASHARE_LLM_API_KEY")
        os.environ["ASHARE_LLM_API_KEY"] = "test-key"
        try:
            settings = RuntimeSettings.load(config_path)
            client = LLMClient.from_settings(settings)
        finally:
            if previous_api_key is None:
                os.environ.pop("ASHARE_LLM_API_KEY", None)
            else:
                os.environ["ASHARE_LLM_API_KEY"] = previous_api_key

        self.assertTrue(settings.fund_graph.llm_enabled)
        self.assertEqual(settings.fund_graph.llm_timeout, 20.0)
        self.assertEqual(settings.fund_graph.llm_retries, 1)
        self.assertTrue(client.enabled)

    def test_runtime_settings_loads_env_placeholders(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "data_dir: ./data",
                        "registry_dir: ./registry",
                        "database:",
                        "  enabled: true",
                        "  url: ${TEST_DATABASE_URL}",
                        "scheduler:",
                        "  portfolio_file: ${TEST_PORTFOLIO_FILE:-examples/fund_portfolio.json}",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["TEST_DATABASE_URL"] = "sqlite:///./env-test.sqlite3"
            try:
                settings = RuntimeSettings.load(config_path)
            finally:
                os.environ.pop("TEST_DATABASE_URL", None)

            self.assertTrue(settings.database.enabled)
            self.assertEqual(settings.database.url, "sqlite:///./env-test.sqlite3")
            self.assertEqual(settings.scheduler.portfolio_file, "examples/fund_portfolio.json")

    def test_runtime_settings_loads_fund_graph_llm_overrides(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "fund_graph:",
                        "  enabled: true",
                        "  llm_enabled: true",
                        "  llm_api_key: config-key",
                        "  llm_model: openai/gpt-5.4-mini",
                        "  llm_base_url: https://example.test/v1",
                        "  llm_timeout: 12",
                        "  llm_retries: 2",
                    ]
                ),
                encoding="utf-8",
            )

            settings = RuntimeSettings.load(config_path)

            self.assertEqual(settings.fund_graph.llm_api_key, "config-key")
            self.assertEqual(settings.fund_graph.llm_model, "openai/gpt-5.4-mini")
            self.assertEqual(settings.fund_graph.llm_base_url, "https://example.test/v1")
            self.assertEqual(settings.fund_graph.llm_timeout, 12.0)
            self.assertEqual(settings.fund_graph.llm_retries, 2)


if __name__ == "__main__":
    unittest.main()
