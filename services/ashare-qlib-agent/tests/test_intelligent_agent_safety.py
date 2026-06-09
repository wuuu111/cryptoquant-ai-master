import unittest

from ashare_qlib_agent.collaboration import SupervisorAgent
from ashare_qlib_agent.llm import LLMClient, safe_json_parse


class IntelligentAgentSafetyTest(unittest.TestCase):
    def test_safe_json_parse_extracts_json_from_text(self):
        parsed = safe_json_parse(
            "模型输出如下：```json\n{\"decision\":\"pause\",\"confidence\":0.4}\n```",
            fallback={"decision": "fallback"},
        )

        self.assertEqual(parsed["decision"], "pause")
        self.assertEqual(parsed["confidence"], 0.4)

    def test_safe_json_parse_returns_fallback_with_raw_response(self):
        parsed = safe_json_parse("not json at all", fallback={"decision": "fallback"})

        self.assertEqual(parsed["decision"], "fallback")
        self.assertIn("raw_response", parsed)
        self.assertIn("not json", parsed["raw_response"])

    def test_llm_system_prompt_includes_global_multi_agent_rules(self):
        client = LLMClient(api_key=None, model="test", base_url="http://example.com", enabled=False)

        prompt = client._system_prompt("你是 MarketDetectAgent。")

        self.assertIn("规则系统负责确定性计算", prompt)
        self.assertIn("LLM 不得直接下单", prompt)
        self.assertIn("所有 LLM 输出必须是结构化 JSON", prompt)
        self.assertIn("你是 MarketDetectAgent。", prompt)

    def test_supervisor_guardrails_override_llm_approve(self):
        supervisor = SupervisorAgent()

        decision = supervisor.apply_guardrails({
            "data_quality_report": {"data_passed": False, "blocking_reasons": ["empty universe"]},
            "hard_risk_passed": False,
            "risk_report": {"hard_risk_check": {"passed": False, "blocking_reasons": ["risk off"]}},
            "order_critic_report": {"decision": "block"},
            "llm_decision": {"decision": "approve", "reasoning_summary": "looks fine"},
        })

        self.assertNotEqual(decision["decision"], "approve")
        self.assertEqual(decision["decision"], "pause")
        self.assertTrue(decision["requires_human_review"])
        self.assertGreaterEqual(len(decision["opposing_evidence"]), 3)


if __name__ == "__main__":
    unittest.main()
