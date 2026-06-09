from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ashare_qlib_agent.http_server import run_server  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the dependency-free fund rotation agent HTTP server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8710)
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
