from __future__ import annotations

import pandas as pd

from .fund_data_loader import FundDataLoader
from .fund_feature_builder import FundFeatureBuilder
from .fund_graph_agent import FundGraphWorkflow
from .llm import LLMClient
from .fund_store import FundStore, database_enabled
from .schemas import InstrumentFeature, PortfolioState, to_jsonable
from .settings import RuntimeSettings


def cycle_from_fund_csv(settings: RuntimeSettings, portfolio: PortfolioState | None = None, account_id: str | None = None) -> dict:
    bundle, features = _load_bundle_and_features_csv(settings)
    return _cycle_from_bundle(bundle, features, settings=settings, portfolio=portfolio, account_id=account_id)


def cycle_from_fund_store(settings: RuntimeSettings, portfolio: PortfolioState | None = None, account_id: str | None = None) -> dict:
    bundle, features = _load_bundle_and_features_store(settings)
    return _cycle_from_bundle(bundle, features, settings=settings, portfolio=portfolio, account_id=account_id)


def cycle_from_settings(settings: RuntimeSettings, portfolio: PortfolioState | None = None, account_id: str | None = None) -> dict:
    effective_portfolio = _resolve_portfolio(settings, portfolio, account_id=account_id)
    if database_enabled(settings.database):
        return cycle_from_fund_store(settings, effective_portfolio, account_id=account_id)
    return cycle_from_fund_csv(settings, effective_portfolio, account_id=account_id)


def feature_snapshot_from_fund_csv(settings: RuntimeSettings, limit: int = 20) -> dict:
    bundle, features = _load_bundle_and_features_csv(settings)
    return _feature_snapshot_from_bundle(bundle, features, settings, limit=limit)


def feature_snapshot_from_fund_store(settings: RuntimeSettings, limit: int = 20) -> dict:
    bundle, features = _load_bundle_and_features_store(settings)
    return _feature_snapshot_from_bundle(bundle, features, settings, limit=limit)


def feature_snapshot_from_settings(settings: RuntimeSettings, limit: int = 20) -> dict:
    if database_enabled(settings.database):
        return feature_snapshot_from_fund_store(settings, limit=limit)
    return feature_snapshot_from_fund_csv(settings, limit=limit)


def latest_cycle_from_store(settings: RuntimeSettings) -> dict | None:
    store = FundStore.from_settings(settings)
    return store.latest_cycle()


def _feature_snapshot_from_bundle(bundle, features: pd.DataFrame, settings: RuntimeSettings, limit: int = 20) -> dict:
    latest = features.groupby("fund_code", as_index=False).tail(1).copy()
    snapshot = _snapshot_from_latest(latest, bundle.fund_pool, bundle.fund_metadata, bundle.benchmark, settings)
    feature_by_code = latest.set_index("fund_code").to_dict("index")
    pool_by_code = bundle.fund_pool.set_index("fund_code").to_dict("index")

    items = []
    for instrument in snapshot.instruments:
        feature_row = feature_by_code.get(instrument.symbol, {})
        pool_row = pool_by_code.get(instrument.symbol, {})
        items.append(
            {
                "fund_code": instrument.symbol,
                "fund_name": pool_row.get("fund_name", instrument.symbol),
                "category": instrument.category,
                "fund_type": instrument.fund_type,
                "risk_level": instrument.risk_level,
                "nav": instrument.close,
                "daily_return": float(feature_row.get("daily_return", 0.0)),
                "return_5d": instrument.factors.get("return_5d", 0.0),
                "return_20d": instrument.factors.get("return_20d", 0.0),
                "return_60d": instrument.factors.get("return_60d", 0.0),
                "return_120d": instrument.factors.get("return_120d", 0.0),
                "volatility_60d": instrument.factors.get("volatility_60d", 0.0),
                "max_drawdown_60d": instrument.factors.get("max_drawdown_60d", 0.0),
                "max_drawdown_120d": instrument.factors.get("max_drawdown_120d", 0.0),
                "ma20": instrument.factors.get("ma20", 0.0),
                "ma60": instrument.factors.get("ma60", 0.0),
                "distance_to_60d_high": instrument.factors.get("distance_to_60d_high", 0.0),
                "purchase_status": instrument.purchase_status,
                "redemption_status": instrument.redemption_status,
                "data_as_of": instrument.data_as_of,
                "stale": instrument.stale,
            }
        )

    ranked_items = sorted(items, key=lambda row: float(row.get("return_20d", 0.0)), reverse=True)
    return {
        "as_of": snapshot.as_of,
        "benchmark_returns": snapshot.benchmark_returns,
        "count": len(ranked_items),
        "items": ranked_items[: max(0, limit)],
    }


def _load_bundle_and_features_csv(settings: RuntimeSettings):
    loader = FundDataLoader(settings.data_dir, settings.fund_data)
    bundle = loader.load()
    features = FundFeatureBuilder().build(bundle.fund_nav)
    return bundle, features


def _load_bundle_and_features_store(settings: RuntimeSettings):
    store = FundStore.from_settings(settings)
    bundle = store.load_bundle()
    features = FundFeatureBuilder().build(bundle.fund_nav)
    return bundle, features


def _cycle_from_bundle(
    bundle,
    features: pd.DataFrame,
    settings: RuntimeSettings,
    portfolio: PortfolioState | None = None,
    account_id: str | None = None,
) -> dict:
    latest = features.groupby("fund_code", as_index=False).tail(1).copy()
    snapshot = _snapshot_from_latest(latest, bundle.fund_pool, bundle.fund_metadata, bundle.benchmark, settings)
    llm = LLMClient.from_settings(settings)
    agent = FundGraphWorkflow(
        portfolio_mode=settings.fund_data.portfolio_mode,
        llm=llm,
        registry_dir=settings.registry_dir,
        max_position_weight=settings.portfolio.max_position_weight,
    )
    result = agent.run_cycle(
        snapshot,
        portfolio or _default_portfolio(settings),
    )
    payload = to_jsonable(result)
    if database_enabled(settings.database) and settings.database.save_cycles:
        store = FundStore.from_settings(settings)
        store.save_cycle_result(payload, portfolio_mode=settings.fund_data.portfolio_mode, as_of=snapshot.as_of)
    return payload


def _snapshot_from_latest(
    latest: pd.DataFrame,
    fund_pool: pd.DataFrame,
    fund_metadata: pd.DataFrame,
    benchmark: pd.DataFrame,
    settings: RuntimeSettings,
):
    from .schemas import MarketSnapshot

    latest_date = pd.to_datetime(latest["date"].max()) if len(latest) else pd.NaT
    as_of = str(latest_date.date()) if pd.notna(latest_date) else ""
    pool_by_code = fund_pool.set_index("fund_code").to_dict("index")
    meta_by_code = fund_metadata.set_index("fund_code").to_dict("index")
    reference_date = pd.to_datetime(settings.fund_data.reference_date) if settings.fund_data.reference_date else pd.Timestamp.today().normalize()
    stale_cutoff = reference_date - pd.Timedelta(days=settings.fund_data.stale_nav_days)
    instruments: list[InstrumentFeature] = []

    for _, row in latest.iterrows():
        code = str(row["fund_code"])
        pool = pool_by_code.get(code, {})
        meta = meta_by_code.get(code, {})
        factors = {
            "return_5d": float(row.get("return_5d", 0.0)),
            "return_20d": float(row.get("return_20d", 0.0)),
            "return_60d": float(row.get("return_60d", 0.0)),
            "return_120d": float(row.get("return_120d", 0.0)),
            "volatility_60d": float(row.get("volatility_60d", 0.0)),
            "max_drawdown_60d": float(row.get("max_drawdown_60d", 0.0)),
            "max_drawdown_120d": float(row.get("max_drawdown_120d", 0.0)),
            "ma20": float(row.get("ma20", 0.0)),
            "ma60": float(row.get("ma60", 0.0)),
            "distance_to_60d_high": float(row.get("distance_to_60d_high", -1.0)),
        }
        row_date = pd.to_datetime(row["date"])
        instruments.append(
            InstrumentFeature(
                symbol=code,
                close=float(row["nav"]),
                pct_chg=float(row.get("daily_return", 0.0)) * 100.0,
                turnover=0.0,
                market_cap=float(meta.get("aum", 0.0)),
                industry=str(pool.get("category", meta.get("category", "UNKNOWN"))),
                category=str(pool.get("category", meta.get("category", "UNKNOWN"))),
                fund_type=str(pool.get("fund_type", meta.get("fund_type", "UNKNOWN"))),
                tracking_index=str(pool.get("tracking_index", "")),
                risk_level=str(pool.get("risk_level", "UNKNOWN")),
                enabled=bool(pool.get("enabled", True)),
                purchase_status=str(meta.get("purchase_status", "open")),
                redemption_status=str(meta.get("redemption_status", "open")),
                data_as_of=str(row_date.date()),
                stale=row_date < stale_cutoff,
                factors=factors,
            )
        )

    benchmark_frame = benchmark.copy()
    benchmark_frame = benchmark_frame[benchmark_frame["index_code"] == settings.fund_data.benchmark_index_code.upper()]
    if benchmark_frame.empty:
        benchmark_frame = benchmark
    benchmark_latest = benchmark_frame.sort_values("date").tail(1)
    benchmark_return = float(benchmark_latest.iloc[0]["daily_return"]) if not benchmark_latest.empty else 0.0
    benchmark_code = str(benchmark_latest.iloc[0]["index_code"]) if not benchmark_latest.empty else settings.fund_data.benchmark_index_code

    return MarketSnapshot(
        as_of=as_of,
        benchmark_returns={benchmark_code: benchmark_return},
        breadth={
            "advance_ratio": float((latest["daily_return"].fillna(0.0) > 0).mean()) if len(latest) else 0.5,
            "limit_up_count": 0.0,
            "limit_down_count": 0.0,
            "turnover_ratio": 1.0,
        },
        instruments=instruments,
    )


def _resolve_portfolio(
    settings: RuntimeSettings,
    portfolio: PortfolioState | None = None,
    *,
    account_id: str | None = None,
) -> PortfolioState:
    if portfolio is not None:
        return portfolio
    if database_enabled(settings.database):
        from .fund_account_service import FundAccountService

        return FundAccountService.from_settings(settings).to_portfolio_state(account_id=account_id or settings.account.default_account_id)
    return _default_portfolio(settings)


def _default_portfolio(settings: RuntimeSettings) -> PortfolioState:
    return PortfolioState(
        cash=settings.portfolio.initial_cash,
        equity=settings.portfolio.initial_cash,
        positions=[],
    )
