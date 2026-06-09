import unittest
from pathlib import Path


class PackagingDependenciesTest(unittest.TestCase):
    def test_api_extra_includes_httpx_for_llm_runtime(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")

        self.assertIn('"httpx>=0.27"', content)


if __name__ == "__main__":
    unittest.main()
