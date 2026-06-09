from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fund_live_cycle import cycle_from_settings
from .fund_sync import FundDataSyncer
from .schemas import PortfolioState, parse_portfolio
from .settings import RuntimeSettings


@dataclass(frozen=True)
class SchedulerRunReport:
    sync: dict[str, Any] | None
    cycle: dict[str, Any]


class FundTaskScheduler:
    def __init__(self, settings: RuntimeSettings, account_id: str | None = None):
        self.settings = settings
        self.account_id = (account_id or settings.account.default_account_id).strip() or settings.account.default_account_id
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> SchedulerRunReport:
        sync_report: dict[str, Any] | None = None
        if self.settings.scheduler.sync_before_cycle:
            sync_report = FundDataSyncer(
                self.settings.data_dir,
                self.settings.fund_data,
                database=self.settings.database,
            ).sync(
                start_date=self.settings.scheduler.start_date or self.settings.start_date,
                end_date=self.settings.scheduler.end_date or self.settings.end_date,
            ).__dict__
        portfolio = _load_scheduler_portfolio(self.settings.scheduler.portfolio_file)
        cycle = cycle_from_settings(self.settings, portfolio=portfolio, account_id=self.account_id)
        return SchedulerRunReport(sync=sync_report, cycle=cycle)

    def start(self) -> bool:
        if not self.settings.scheduler.enabled or self._thread is not None:
            return False
        self._thread = threading.Thread(target=self._run_loop, name="fund-task-scheduler", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def wait(self) -> None:
        if self._thread is not None:
            self._thread.join()

    def _run_loop(self) -> None:
        if self.settings.scheduler.run_on_startup:
            self.run_once()
        interval_seconds = max(60, int(self.settings.scheduler.interval_minutes) * 60)
        while not self._stop_event.wait(interval_seconds):
            self.run_once()


def _load_scheduler_portfolio(path: str) -> PortfolioState | None:
    if not path.strip():
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Scheduler portfolio file must contain a JSON object: {path}")
    return parse_portfolio(payload)
