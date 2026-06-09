from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .fund_fixtures import write_sample_fund_data
from .fund_live_cycle import cycle_from_settings, feature_snapshot_from_settings, latest_cycle_from_store
from .fund_scheduler import FundTaskScheduler
from .fund_store import FundStore, database_enabled
from .fund_sync import FundDataSyncer
from .schemas import parse_portfolio
from .settings import RuntimeSettings


class FundHttpHandler(BaseHTTPRequestHandler):
    server_version = "FundRotationAgent/0.1"

    def do_GET(self) -> None:
        if self.path == "/":
            self._json(
                {
                    "name": "Fund Rotation Agent",
                    "ok": True,
                    "endpoints": {
                        "health": "GET /health",
                        "fund_features": "GET /fund-features",
                        "fund_cycle": "POST /fund-cycle",
                        "sync_fund_data": "POST /sync-fund-data",
                        "sample_fund_data": "POST /sample-fund-data",
                    },
                }
            )
            return
        if self.path.startswith("/health"):
            settings = _load_settings()
            payload = {
                "ok": True,
                "service": "fund_rotation_agent",
                "database_enabled": database_enabled(settings.database),
                "scheduler_enabled": settings.scheduler.enabled,
            }
            if database_enabled(settings.database):
                payload["database"] = FundStore.from_settings(settings).status().__dict__
            self._json(payload)
            return
        if self.path.startswith("/fund-features"):
            settings = _load_settings()
            self._json(feature_snapshot_from_settings(settings, limit=20))
            return
        if self.path.startswith("/latest-cycle"):
            settings = _load_settings()
            self._json(latest_cycle_from_store(settings) or {})
            return
        self._json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            config_path = str(payload.get("config_path", ""))
            settings = _load_settings(config_path)

            if self.path == "/fund-cycle":
                portfolio = parse_portfolio(payload.get("portfolio", {}))
                self._json(cycle_from_settings(settings, portfolio if portfolio.equity > 0 or portfolio.cash > 0 or portfolio.positions else None))
                return
            if self.path == "/sync-fund-data":
                sync_report = FundDataSyncer(settings.data_dir, settings.fund_data, database=settings.database).sync(
                    start_date=str(payload.get("start_date", settings.start_date)),
                    end_date=str(payload.get("end_date", settings.end_date)),
                )
                self._json(sync_report.__dict__)
                return
            if self.path == "/sample-fund-data":
                sample_report = write_sample_fund_data(
                    settings.data_dir,
                    periods=max(60, int(payload.get("days", 180))),
                    end_date=str(payload.get("end_date", "")) or None,
                )
                self._json(sample_report)
                return
            if self.path == "/scheduler/run-once":
                self._json(FundTaskScheduler(settings).run_once().__dict__)
                return

            self._json({"error": "Not found"}, status=404)
        except Exception as error:  # pragma: no cover
            self._json({"error": str(error)}, status=500)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[fund-agent] " + format % args + "\n")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "127.0.0.1", port: int = 8710) -> None:
    server = ThreadingHTTPServer((host, port), FundHttpHandler)
    print(f"Fund rotation agent listening on http://{host}:{port}")
    server.serve_forever()


def _default_config_path() -> str:
    return os.environ.get("FUND_AGENT_CONFIG", "config.real-local.yaml")


def _load_settings(config_path: str = "") -> RuntimeSettings:
    return RuntimeSettings.load(config_path or _default_config_path())
