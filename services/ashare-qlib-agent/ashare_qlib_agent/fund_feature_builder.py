from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FundFeatureReport:
    rows: int
    latest_date: str


class FundFeatureBuilder:
    def build(self, nav_frame: pd.DataFrame) -> pd.DataFrame:
        if nav_frame.empty:
            return nav_frame.copy()
        rows = []
        for _, group in nav_frame.groupby("fund_code", sort=False):
            rows.append(self._build_one(group))
        return pd.concat(rows, ignore_index=True).sort_values(["fund_code", "date"]).reset_index(drop=True)

    def _build_one(self, frame: pd.DataFrame) -> pd.DataFrame:
        row = frame.copy().sort_values("date")
        nav = row["nav"].astype(float)
        daily_return = row["daily_return"].astype(float)
        row["return_20d"] = nav.pct_change(20)
        row["return_60d"] = nav.pct_change(60)
        row["return_120d"] = nav.pct_change(120)
        row["volatility_60d"] = daily_return.rolling(60).std()
        rolling_max_120 = nav.rolling(120, min_periods=1).max()
        row["max_drawdown_120d"] = nav / rolling_max_120 - 1.0
        row["max_drawdown_60d"] = (nav / nav.rolling(60, min_periods=1).max()) - 1.0
        row["ma20"] = nav.rolling(20).mean()
        row["ma60"] = nav.rolling(60).mean()
        row["distance_to_60d_high"] = nav / nav.rolling(60, min_periods=1).max() - 1.0
        row["return_5d"] = nav.pct_change(5)
        return row
