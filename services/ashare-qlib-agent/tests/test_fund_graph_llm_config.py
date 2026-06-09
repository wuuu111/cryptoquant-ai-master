import unittest

from ashare_qlib_agent.llm import LLMClient
from ashare_qlib_agent.settings import FundGraphSettings, RuntimeSettings


class FundGraphLLMConfigTest(unittest.TestCase):
    def test_llm_client_prefers_runtime_settings(self):
        settings = RuntimeSettings(
            fund_graph=FundGraphSettings(
                enabled=True,
                llm_enabled=True,
                llm_api_key="runtime-key",
                llm_model="openai/gpt-5.4-mini",
                llm_base_url="https://example.test/v1",
                llm_timeout=9.0,
                llm_retries=3,
            )
        )

        client = LLMClient.from_settings(settings)

        self.assertTrue(client.enabled)
        self.assertEqual(client.api_key, "runtime-key")
        self.assertEqual(client.model, "openai/gpt-5.4-mini")
        self.assertEqual(client.base_url, "https://example.test/v1")
        self.assertEqual(client.timeout, 9.0)
        self.assertEqual(client.retries, 3)


if __name__ == "__main__":
    unittest.main()
