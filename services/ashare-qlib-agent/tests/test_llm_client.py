import unittest
from unittest.mock import patch

import httpx

from ashare_qlib_agent.llm import LLMClient


class LLMClientTest(unittest.TestCase):
    def test_transport_failure_soft_disables_remaining_calls(self):
        client = LLMClient(
            api_key="test-key",
            model="test-model",
            base_url="https://example.invalid",
            enabled=True,
            timeout=0.01,
            retries=0,
        )

        with patch("ashare_qlib_agent.llm.httpx.post", side_effect=httpx.ConnectError("boom")) as mocked_post:
            first = client.explain_fund_market_regime({"reason": "range"})
            second = client.explain_fund_factor_ranking({"scores": []})

        self.assertIn("_llm_error", first)
        self.assertIn("_llm_error", second)
        self.assertEqual(mocked_post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
