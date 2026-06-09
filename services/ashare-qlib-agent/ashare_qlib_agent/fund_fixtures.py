from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def write_sample_fund_data(
    data_dir: Path,
    *,
    periods: int = 180,
    end_date: str | None = None,
) -> dict[str, object]:
    """Create deterministic fund CSV inputs for local offline validation."""

    data_dir.mkdir(parents=True, exist_ok=True)
    end = pd.to_datetime(end_date).normalize() if end_date else pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=periods)

    fund_rows = [
        {
            "fund_code": "EQCORE",
            "fund_name": "Core Equity 300",
            "category": "equity",
            "fund_type": "ETF",
            "tracking_index": "CSI300",
            "risk_level": "high",
            "enabled": 1,
        },
        {
            "fund_code": "EQTECH",
            "fund_name": "Growth Tech Select",
            "category": "equity",
            "fund_type": "LOF",
            "tracking_index": "STAR50",
            "risk_level": "high",
            "enabled": 1,
        },
        {
            "fund_code": "BOND01",
            "fund_name": "Stable Bond Plus",
            "category": "bond",
            "fund_type": "LOF",
            "tracking_index": "",
            "risk_level": "low",
            "enabled": 1,
        },
        {
            "fund_code": "GOLD01",
            "fund_name": "Gold Hedge ETF",
            "category": "commodity",
            "fund_type": "ETF",
            "tracking_index": "AU9999",
            "risk_level": "medium",
            "enabled": 1,
        },
        {
            "fund_code": "CASH01",
            "fund_name": "Cash Anchor",
            "category": "cash",
            "fund_type": "money_market",
            "tracking_index": "",
            "risk_level": "low",
            "enabled": 1,
        },
        {
            "fund_code": "QDIIUS",
            "fund_name": "Global Nasdaq QDII",
            "category": "qdii",
            "fund_type": "QDII",
            "tracking_index": "NASDAQ100",
            "risk_level": "high",
            "enabled": 1,
        },
    ]
    metadata_rows = [
        {
            "fund_code": "EQCORE",
            "fund_name": "Core Equity 300",
            "category": "equity",
            "fund_type": "ETF",
            "fee": 0.60,
            "aum": 28_000_000,
            "manager": "Alpha",
            "purchase_status": "open",
            "redemption_status": "open",
        },
        {
            "fund_code": "EQTECH",
            "fund_name": "Growth Tech Select",
            "category": "equity",
            "fund_type": "LOF",
            "fee": 0.80,
            "aum": 18_000_000,
            "manager": "Beta",
            "purchase_status": "open",
            "redemption_status": "open",
        },
        {
            "fund_code": "BOND01",
            "fund_name": "Stable Bond Plus",
            "category": "bond",
            "fund_type": "LOF",
            "fee": 0.30,
            "aum": 22_000_000,
            "manager": "Gamma",
            "purchase_status": "open",
            "redemption_status": "open",
        },
        {
            "fund_code": "GOLD01",
            "fund_name": "Gold Hedge ETF",
            "category": "commodity",
            "fund_type": "ETF",
            "fee": 0.50,
            "aum": 12_000_000,
            "manager": "Delta",
            "purchase_status": "open",
            "redemption_status": "open",
        },
        {
            "fund_code": "CASH01",
            "fund_name": "Cash Anchor",
            "category": "cash",
            "fund_type": "money_market",
            "fee": 0.10,
            "aum": 35_000_000,
            "manager": "Epsilon",
            "purchase_status": "open",
            "redemption_status": "open",
        },
        {
            "fund_code": "QDIIUS",
            "fund_name": "Global Nasdaq QDII",
            "category": "qdii",
            "fund_type": "QDII",
            "fee": 0.90,
            "aum": 16_000_000,
            "manager": "Zeta",
            "purchase_status": "open",
            "redemption_status": "open",
        },
    ]

    pd.DataFrame(fund_rows).to_csv(data_dir / "fund_pool.csv", index=False)
    pd.DataFrame(metadata_rows).to_csv(data_dir / "fund_metadata.csv", index=False)

    nav_specs = {
        "EQCORE": (0.0008, 0.0060, 20260601),
        "EQTECH": (0.0011, 0.0090, 20260602),
        "BOND01": (0.00018, 0.0012, 20260603),
        "GOLD01": (0.00045, 0.0045, 20260604),
        "CASH01": (0.00006, 0.00015, 20260605),
        "QDIIUS": (0.0009, 0.0080, 20260606),
    }
    nav_frames: list[pd.DataFrame] = []
    for code, (drift, vol, seed) in nav_specs.items():
        rng = np.random.default_rng(seed)
        returns = rng.normal(drift, vol, size=len(dates))
        nav = np.cumprod(1.0 + returns)
        frame = pd.DataFrame(
            {
                "date": dates,
                "fund_code": code,
                "nav": nav.round(6),
                "daily_return": returns.round(6),
            }
        )
        nav_frames.append(frame)
    nav_frame = pd.concat(nav_frames, ignore_index=True).sort_values(["fund_code", "date"])
    nav_frame.to_csv(data_dir / "fund_nav_daily.csv", index=False)

    benchmark_rng = np.random.default_rng(20260607)
    benchmark_returns = benchmark_rng.normal(0.00065, 0.0055, size=len(dates))
    benchmark_close = 1000 * np.cumprod(1.0 + benchmark_returns)
    benchmark_frame = pd.DataFrame(
        {
            "date": dates,
            "index_code": "BENCH",
            "close": benchmark_close.round(3),
            "daily_return": benchmark_returns.round(6),
        }
    )
    benchmark_frame.to_csv(data_dir / "benchmark_index.csv", index=False)

    return {
        "funds": [row["fund_code"] for row in fund_rows],
        "fund_count": len(fund_rows),
        "nav_rows": int(len(nav_frame)),
        "benchmark_rows": int(len(benchmark_frame)),
        "as_of": str(dates[-1].date()),
        "files": [
            str(data_dir / "fund_pool.csv"),
            str(data_dir / "fund_nav_daily.csv"),
            str(data_dir / "fund_metadata.csv"),
            str(data_dir / "benchmark_index.csv"),
        ],
        "source": "offline_sample_fund_data",
    }
