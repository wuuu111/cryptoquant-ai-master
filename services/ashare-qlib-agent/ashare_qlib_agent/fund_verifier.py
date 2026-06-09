from __future__ import annotations

from typing import Any

from .fund_live_cycle import cycle_from_settings, latest_cycle_from_store
from .fund_store import FundStore
from .fund_sync import AkshareFundDataSource, FundDataSyncer
from .schemas import PortfolioState
from .settings import RuntimeSettings


def verify_postgres(
    settings: RuntimeSettings,
    portfolio: PortfolioState | None = None,
    account_id: str | None = None,
    source: AkshareFundDataSource | None = None,
    skip_sync: bool = False,
) -> dict[str, Any]:
    store = FundStore.from_settings(settings)
    store.init_schema()

    sync_payload: dict[str, Any] | None = None
    if not skip_sync:
        report = FundDataSyncer(
            settings.data_dir,
            settings.fund_data,
            source=source,
            database=settings.database,
        ).sync(
            start_date=settings.start_date,
            end_date=settings.end_date,
        )
        sync_payload = report.__dict__

    cycle = cycle_from_settings(settings, portfolio=portfolio, account_id=account_id)
    latest = latest_cycle_from_store(settings)
    return {
        "database": store.status().__dict__,
        "row_counts": store.table_row_counts(),
        "sync_report": sync_payload,
        "cycle": cycle,
        "latest_cycle_id": latest.get("cycle_id") if latest else "",
        "latest_review": latest.get("review", {}).get("summary", "") if latest else "",
    }
