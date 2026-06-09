from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .settings import FundDataSettings


@dataclass(frozen=True)
class FundDataBundle:
    fund_pool: pd.DataFrame
    fund_nav: pd.DataFrame
    fund_metadata: pd.DataFrame
    benchmark: pd.DataFrame


class FundDataLoader:
    def __init__(self, data_dir: Path, settings: FundDataSettings):
        self.data_dir = data_dir
        self.settings = settings

    def load(self) -> FundDataBundle:
        fund_pool = self._read_csv(
            self.settings.fund_pool_file,
            required={"fund_code", "fund_name", "category", "fund_type", "tracking_index", "risk_level", "enabled"},
        )
        fund_nav = self._read_csv(
            self.settings.fund_nav_file,
            required={"date", "fund_code", "nav", "daily_return"},
            parse_dates=["date"],
        )
        fund_metadata = self._read_csv(
            self.settings.fund_metadata_file,
            required={
                "fund_code",
                "fund_name",
                "category",
                "fund_type",
                "fee",
                "aum",
                "manager",
                "purchase_status",
                "redemption_status",
            },
        )
        benchmark = self._read_csv(
            self.settings.benchmark_file,
            required={"date", "index_code", "close", "daily_return"},
            parse_dates=["date"],
        )

        fund_pool = fund_pool.copy()
        fund_nav = fund_nav.copy()
        fund_metadata = fund_metadata.copy()
        benchmark = benchmark.copy()

        fund_pool["fund_code"] = fund_pool["fund_code"].astype(str).str.strip().str.upper()
        fund_metadata["fund_code"] = fund_metadata["fund_code"].astype(str).str.strip().str.upper()
        fund_nav["fund_code"] = fund_nav["fund_code"].astype(str).str.strip().str.upper()
        fund_pool["enabled"] = fund_pool["enabled"].astype(int).astype(bool)
        fund_pool = fund_pool[fund_pool["enabled"]].drop_duplicates(subset=["fund_code"])

        enabled_codes = set(fund_pool["fund_code"])
        fund_metadata = fund_metadata[fund_metadata["fund_code"].isin(enabled_codes)].drop_duplicates(subset=["fund_code"])
        fund_nav = fund_nav[fund_nav["fund_code"].isin(enabled_codes)].sort_values(["fund_code", "date"])
        benchmark["index_code"] = benchmark["index_code"].astype(str).str.strip().str.upper()

        return FundDataBundle(
            fund_pool=fund_pool.reset_index(drop=True),
            fund_nav=fund_nav.reset_index(drop=True),
            fund_metadata=fund_metadata.reset_index(drop=True),
            benchmark=benchmark.sort_values(["index_code", "date"]).reset_index(drop=True),
        )

    def _read_csv(self, filename: str, required: set[str], parse_dates: list[str] | None = None) -> pd.DataFrame:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Fund data file not found: {path}")
        frame = pd.read_csv(path, parse_dates=parse_dates or [])
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{filename} missing required columns: {missing}")
        return frame
