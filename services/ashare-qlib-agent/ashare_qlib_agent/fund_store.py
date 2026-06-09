from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, delete, func, insert, select

from .fund_data_loader import FundDataBundle
from .settings import DatabaseSettings, RuntimeSettings


@dataclass(frozen=True)
class FundStoreStatus:
    database_url: str
    schema: str
    latest_sync_at: str
    latest_cycle_at: str


class FundStore:
    def __init__(self, url: str, schema: str = "public"):
        self.engine = create_engine(url, future=True)
        self.schema = schema if schema and self.engine.dialect.name != "sqlite" else ""
        self.metadata = MetaData(schema=self.schema or None)
        self.fund_pool = Table(
            "fund_pool",
            self.metadata,
            Column("fund_code", String(32), primary_key=True),
            Column("fund_name", String(255), nullable=False),
            Column("category", String(32), nullable=False),
            Column("fund_type", String(128), nullable=False),
            Column("tracking_index", String(255), nullable=False),
            Column("risk_level", String(32), nullable=False),
            Column("enabled", Boolean, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.fund_metadata = Table(
            "fund_metadata",
            self.metadata,
            Column("fund_code", String(32), primary_key=True),
            Column("fund_name", String(255), nullable=False),
            Column("category", String(32), nullable=False),
            Column("fund_type", String(128), nullable=False),
            Column("fee", Float, nullable=False),
            Column("aum", Float, nullable=False),
            Column("manager", String(255), nullable=False),
            Column("purchase_status", String(64), nullable=False),
            Column("redemption_status", String(64), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.fund_nav_daily = Table(
            "fund_nav_daily",
            self.metadata,
            Column("fund_code", String(32), primary_key=True),
            Column("date", Date, primary_key=True),
            Column("nav", Float, nullable=False),
            Column("daily_return", Float, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.benchmark_index_daily = Table(
            "benchmark_index_daily",
            self.metadata,
            Column("index_code", String(32), primary_key=True),
            Column("date", Date, primary_key=True),
            Column("close", Float, nullable=False),
            Column("daily_return", Float, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.sync_runs = Table(
            "fund_sync_runs",
            self.metadata,
            Column("sync_id", Integer, primary_key=True, autoincrement=True),
            Column("completed_at", DateTime(timezone=True), nullable=False),
            Column("as_of", String(32), nullable=False),
            Column("fund_count", Integer, nullable=False),
            Column("nav_rows", Integer, nullable=False),
            Column("benchmark_rows", Integer, nullable=False),
            Column("files_json", Text, nullable=False),
            Column("skipped_json", Text, nullable=False),
        )
        self.cycle_runs = Table(
            "fund_cycle_runs",
            self.metadata,
            Column("cycle_id", String(128), primary_key=True),
            Column("as_of", String(32), nullable=False),
            Column("portfolio_mode", String(64), nullable=False),
            Column("market_regime", String(64), nullable=False),
            Column("market_gate", String(64), nullable=False),
            Column("review_summary", Text, nullable=False),
            Column("cycle_json", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.rebalance_suggestions = Table(
            "fund_rebalance_suggestions",
            self.metadata,
            Column("suggestion_id", Integer, primary_key=True, autoincrement=True),
            Column("cycle_id", String(128), nullable=False),
            Column("symbol", String(32), nullable=False),
            Column("action", String(32), nullable=False),
            Column("blocked", Boolean, nullable=False),
            Column("reason", Text, nullable=False),
            Column("current_weight", Float, nullable=False),
            Column("target_weight", Float, nullable=False),
            Column("delta_weight", Float, nullable=False),
            Column("current_value", Float, nullable=False),
            Column("target_value", Float, nullable=False),
            Column("delta_value", Float, nullable=False),
            Column("applied", Boolean, nullable=False, default=False),
            Column("applied_trade_id", String(128), nullable=False, default=""),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.accounts = Table(
            "fund_accounts",
            self.metadata,
            Column("account_id", String(128), primary_key=True),
            Column("base_currency", String(16), nullable=False),
            Column("target_total_assets", Float, nullable=False),
            Column("cash_balance", Float, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.trade_ledger = Table(
            "fund_trade_ledger",
            self.metadata,
            Column("trade_id", String(128), primary_key=True),
            Column("account_id", String(128), nullable=False, index=True),
            Column("symbol", String(32), nullable=False, index=True),
            Column("fund_name", String(255), nullable=False),
            Column("side", String(16), nullable=False),
            Column("amount", Float, nullable=False),
            Column("units", Float, nullable=False),
            Column("price", Float, nullable=False),
            Column("source", String(64), nullable=False),
            Column("suggestion_id", String(128), nullable=False, default=""),
            Column("note", Text, nullable=False, default=""),
            Column("trade_time", DateTime(timezone=True), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.position_snapshots = Table(
            "fund_positions",
            self.metadata,
            Column("position_id", Integer, primary_key=True, autoincrement=True),
            Column("account_id", String(128), nullable=False, index=True),
            Column("symbol", String(32), nullable=False, index=True),
            Column("fund_name", String(255), nullable=False),
            Column("units", Float, nullable=False),
            Column("cost_basis", Float, nullable=False),
            Column("average_cost", Float, nullable=False),
            Column("last_nav", Float, nullable=False),
            Column("market_value", Float, nullable=False),
            Column("unrealized_pnl", Float, nullable=False),
            Column("snapshot_at", DateTime(timezone=True), nullable=False),
            Column("applied_trade_id", String(128), nullable=False, default=""),
        )

    @classmethod
    def from_settings(cls, settings: RuntimeSettings) -> "FundStore":
        if not settings.database.url:
            raise ValueError("database.url is required when database.enabled=true")
        return cls(settings.database.url, schema=settings.database.schema)

    def init_schema(self) -> None:
        self.metadata.create_all(self.engine)

    def write_sync_data(
        self,
        fund_pool: pd.DataFrame,
        fund_nav: pd.DataFrame,
        fund_metadata: pd.DataFrame,
        benchmark: pd.DataFrame,
        report: dict[str, Any],
    ) -> None:
        now = _utcnow()
        with self.engine.begin() as connection:
            self.metadata.create_all(connection)
            connection.execute(delete(self.fund_pool))
            connection.execute(delete(self.fund_metadata))
            connection.execute(delete(self.fund_nav_daily))
            connection.execute(delete(self.benchmark_index_daily))
            if not fund_pool.empty:
                connection.execute(insert(self.fund_pool), _pool_records(fund_pool, now))
            if not fund_metadata.empty:
                connection.execute(insert(self.fund_metadata), _metadata_records(fund_metadata, now))
            if not fund_nav.empty:
                connection.execute(insert(self.fund_nav_daily), _nav_records(fund_nav, now))
            if not benchmark.empty:
                connection.execute(insert(self.benchmark_index_daily), _benchmark_records(benchmark, now))
            connection.execute(
                insert(self.sync_runs),
                {
                    "completed_at": now,
                    "as_of": str(report.get("as_of", "")),
                    "fund_count": int(report.get("fund_count", 0)),
                    "nav_rows": int(report.get("nav_rows", 0)),
                    "benchmark_rows": int(report.get("benchmark_rows", 0)),
                    "files_json": json.dumps(report.get("files", []), ensure_ascii=False),
                    "skipped_json": json.dumps(report.get("skipped", []), ensure_ascii=False),
                },
            )

    def load_bundle(self) -> FundDataBundle:
        self.init_schema()
        with self.engine.begin() as connection:
            fund_pool = pd.read_sql(select(self.fund_pool), connection)
            fund_nav = pd.read_sql(select(self.fund_nav_daily), connection, parse_dates=["date"])
            fund_metadata = pd.read_sql(select(self.fund_metadata), connection)
            benchmark = pd.read_sql(select(self.benchmark_index_daily), connection, parse_dates=["date"])
        if fund_pool.empty or fund_nav.empty or fund_metadata.empty or benchmark.empty:
            raise ValueError("Fund database is empty. Run sync-fund-data before loading from PostgreSQL.")
        return FundDataBundle(
            fund_pool=fund_pool.sort_values("fund_code").reset_index(drop=True),
            fund_nav=fund_nav.sort_values(["fund_code", "date"]).reset_index(drop=True),
            fund_metadata=fund_metadata.sort_values("fund_code").reset_index(drop=True),
            benchmark=benchmark.sort_values(["index_code", "date"]).reset_index(drop=True),
        )

    def save_cycle_result(self, cycle_payload: dict[str, Any], portfolio_mode: str, as_of: str) -> None:
        now = _utcnow()
        cycle_id = str(cycle_payload.get("cycle_id", ""))
        market = cycle_payload.get("market", {})
        review = cycle_payload.get("review", {})
        suggestions = cycle_payload.get("suggestions", [])
        with self.engine.begin() as connection:
            self.metadata.create_all(connection)
            connection.execute(delete(self.rebalance_suggestions).where(self.rebalance_suggestions.c.cycle_id == cycle_id))
            connection.execute(delete(self.cycle_runs).where(self.cycle_runs.c.cycle_id == cycle_id))
            connection.execute(
                insert(self.cycle_runs),
                {
                    "cycle_id": cycle_id,
                    "as_of": as_of,
                    "portfolio_mode": portfolio_mode,
                    "market_regime": str(market.get("regime", "")),
                    "market_gate": str(market.get("gate", "")),
                    "review_summary": str(review.get("summary", "")),
                    "cycle_json": json.dumps(cycle_payload, ensure_ascii=False),
                    "created_at": now,
                },
            )
            suggestion_rows = []
            for item in suggestions:
                suggestion_rows.append(
                    {
                        "cycle_id": cycle_id,
                        "symbol": str(item.get("symbol", "")),
                        "action": str(item.get("action", "")),
                        "blocked": bool(item.get("blocked", False)),
                        "reason": str(item.get("reason", "")),
                        "current_weight": float(item.get("current_weight", 0.0)),
                        "target_weight": float(item.get("target_weight", 0.0)),
                        "delta_weight": float(item.get("delta_weight", 0.0)),
                        "current_value": float(item.get("current_value", 0.0)),
                        "target_value": float(item.get("target_value", 0.0)),
                        "delta_value": float(item.get("delta_value", 0.0)),
                        "applied": bool(item.get("applied", False)),
                        "applied_trade_id": str(item.get("applied_trade_id", "")),
                        "created_at": now,
                    }
                )
            if suggestion_rows:
                connection.execute(insert(self.rebalance_suggestions), suggestion_rows)

    def latest_cycle(self) -> dict[str, Any] | None:
        self.init_schema()
        query = select(self.cycle_runs.c.cycle_json).order_by(self.cycle_runs.c.created_at.desc()).limit(1)
        with self.engine.begin() as connection:
            row = connection.execute(query).first()
        if row is None:
            return None
        payload = row[0]
        cycle_payload = json.loads(payload) if isinstance(payload, str) else None
        if not isinstance(cycle_payload, dict):
            return None
        cycle_id = str(cycle_payload.get("cycle_id", ""))
        if not cycle_id:
            return cycle_payload
        with self.engine.begin() as connection:
            suggestion_rows = connection.execute(
                select(self.rebalance_suggestions)
                .where(self.rebalance_suggestions.c.cycle_id == cycle_id)
                .order_by(self.rebalance_suggestions.c.suggestion_id.asc())
            ).mappings().all()
        if suggestion_rows and isinstance(cycle_payload.get("suggestions"), list):
            merged = []
            for item, row_data in zip(cycle_payload["suggestions"], suggestion_rows):
                next_item = dict(item)
                next_item["suggestion_id"] = int(row_data["suggestion_id"])
                next_item["applied"] = bool(row_data["applied"])
                next_item["applied_trade_id"] = str(row_data["applied_trade_id"])
                merged.append(next_item)
            cycle_payload["suggestions"] = merged
        return cycle_payload

    def latest_nav_by_symbol(self, symbols: list[str]) -> dict[str, float]:
        self.init_schema()
        if not symbols:
            return {}
        unique_symbols = sorted({str(item) for item in symbols if str(item).strip()})
        if not unique_symbols:
            return {}
        subquery = (
            select(
                self.fund_nav_daily.c.fund_code,
                func.max(self.fund_nav_daily.c.date).label("max_date"),
            )
            .where(self.fund_nav_daily.c.fund_code.in_(unique_symbols))
            .group_by(self.fund_nav_daily.c.fund_code)
            .subquery()
        )
        query = (
            select(self.fund_nav_daily.c.fund_code, self.fund_nav_daily.c.nav)
            .join(
                subquery,
                (self.fund_nav_daily.c.fund_code == subquery.c.fund_code)
                & (self.fund_nav_daily.c.date == subquery.c.max_date),
            )
        )
        with self.engine.begin() as connection:
            rows = connection.execute(query).all()
        return {str(code): float(nav) for code, nav in rows}

    def latest_nav(self, symbol: str) -> float:
        payload = self.latest_nav_by_symbol([symbol])
        return float(payload.get(symbol, 0.0))

    def latest_fund_name(self, symbol: str) -> str:
        self.init_schema()
        with self.engine.begin() as connection:
            pool_row = connection.execute(
                select(self.fund_pool.c.fund_name)
                .where(self.fund_pool.c.fund_code == symbol)
                .limit(1)
            ).first()
            if pool_row is not None and pool_row[0]:
                return str(pool_row[0])
            metadata_row = connection.execute(
                select(self.fund_metadata.c.fund_name)
                .where(self.fund_metadata.c.fund_code == symbol)
                .limit(1)
            ).first()
        if metadata_row is not None and metadata_row[0]:
            return str(metadata_row[0])
        return symbol

    def status(self) -> FundStoreStatus:
        self.init_schema()
        latest_sync_at = ""
        latest_cycle_at = ""
        with self.engine.begin() as connection:
            sync_row = connection.execute(
                select(self.sync_runs.c.completed_at).order_by(self.sync_runs.c.completed_at.desc()).limit(1)
            ).first()
            cycle_row = connection.execute(
                select(self.cycle_runs.c.created_at).order_by(self.cycle_runs.c.created_at.desc()).limit(1)
            ).first()
        if sync_row is not None and sync_row[0] is not None:
            latest_sync_at = _datetime_to_iso(sync_row[0])
        if cycle_row is not None and cycle_row[0] is not None:
            latest_cycle_at = _datetime_to_iso(cycle_row[0])
        return FundStoreStatus(
            database_url=self.engine.url.render_as_string(hide_password=True),
            schema=self.schema or "",
            latest_sync_at=latest_sync_at,
            latest_cycle_at=latest_cycle_at,
        )

    def table_row_counts(self) -> dict[str, int]:
        self.init_schema()
        tables = {
            "fund_pool": self.fund_pool,
            "fund_metadata": self.fund_metadata,
            "fund_nav_daily": self.fund_nav_daily,
            "benchmark_index_daily": self.benchmark_index_daily,
            "fund_sync_runs": self.sync_runs,
            "fund_cycle_runs": self.cycle_runs,
            "fund_rebalance_suggestions": self.rebalance_suggestions,
            "fund_accounts": self.accounts,
            "fund_trade_ledger": self.trade_ledger,
            "fund_positions": self.position_snapshots,
        }
        counts: dict[str, int] = {}
        with self.engine.begin() as connection:
            for name, table in tables.items():
                result = connection.execute(select(func.count()).select_from(table)).scalar_one()
                counts[name] = int(result)
        return counts


def database_enabled(database: DatabaseSettings) -> bool:
    return database.enabled and bool(database.url.strip())


def _pool_records(frame: pd.DataFrame, now: datetime) -> list[dict[str, Any]]:
    records = []
    for row in frame.to_dict("records"):
        records.append(
            {
                "fund_code": str(row["fund_code"]),
                "fund_name": str(row["fund_name"]),
                "category": str(row["category"]),
                "fund_type": str(row["fund_type"]),
                "tracking_index": str(row.get("tracking_index", "")),
                "risk_level": str(row.get("risk_level", "")),
                "enabled": bool(row.get("enabled", True)),
                "updated_at": now,
            }
        )
    return records


def _metadata_records(frame: pd.DataFrame, now: datetime) -> list[dict[str, Any]]:
    records = []
    for row in frame.to_dict("records"):
        records.append(
            {
                "fund_code": str(row["fund_code"]),
                "fund_name": str(row["fund_name"]),
                "category": str(row["category"]),
                "fund_type": str(row["fund_type"]),
                "fee": float(row.get("fee", 0.0)),
                "aum": float(row.get("aum", 0.0)),
                "manager": str(row.get("manager", "")),
                "purchase_status": str(row.get("purchase_status", "open")),
                "redemption_status": str(row.get("redemption_status", "open")),
                "updated_at": now,
            }
        )
    return records


def _nav_records(frame: pd.DataFrame, now: datetime) -> list[dict[str, Any]]:
    records = []
    for row in frame.to_dict("records"):
        records.append(
            {
                "fund_code": str(row["fund_code"]),
                "date": _coerce_date(row["date"]),
                "nav": float(row["nav"]),
                "daily_return": float(row.get("daily_return", 0.0)),
                "updated_at": now,
            }
        )
    return records


def _benchmark_records(frame: pd.DataFrame, now: datetime) -> list[dict[str, Any]]:
    records = []
    for row in frame.to_dict("records"):
        records.append(
            {
                "index_code": str(row["index_code"]),
                "date": _coerce_date(row["date"]),
                "close": float(row["close"]),
                "daily_return": float(row.get("daily_return", 0.0)),
                "updated_at": now,
            }
        )
    return records


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return pd.Timestamp(value).date()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _datetime_to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
