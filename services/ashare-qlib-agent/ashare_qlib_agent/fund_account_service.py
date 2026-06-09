from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import delete, insert, select, update

from .fund_ledger import (
    AccountBook,
    LedgerTrade,
    PositionSnapshot,
    TradeSide,
    apply_trade_to_account,
    new_trade_id,
    rebuild_positions,
    summarize_account_pnl,
    utcnow_iso,
)
from .fund_store import FundStore
from .schemas import PortfolioState, Position
from .settings import RuntimeSettings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FundAccountService:
    def __init__(self, store: FundStore, settings: RuntimeSettings):
        self.store = store
        self.settings = settings
        self.store.init_schema()

    @classmethod
    def from_settings(cls, settings: RuntimeSettings) -> "FundAccountService":
        return cls(FundStore.from_settings(settings), settings)

    def get_account(self, account_id: str = "default") -> dict[str, Any]:
        account_id = self._normalize_account_id(account_id)
        account = self._ensure_account(account_id)
        positions = self._positions(account_id, account.target_total_assets)
        trades = self._trades(account_id)
        pnl = summarize_account_pnl(
            initial_total_assets=account.target_total_assets,
            cash_balance=account.cash_balance,
            positions=positions,
            trades=trades,
        )
        payload = asdict(account)
        payload["positions_count"] = len(positions)
        payload["pnl"] = pnl
        return payload

    def upsert_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        account_id = self._normalize_account_id(str(payload.get("account_id", "")))
        existing = self._load_account(account_id)
        now = _utcnow()
        if existing is None:
            account = AccountBook(
                account_id=account_id,
                base_currency=str(payload.get("base_currency", self.settings.account.base_currency)),
                target_total_assets=float(payload.get("target_total_assets", self.settings.portfolio.initial_cash)),
                cash_balance=float(payload.get("cash_balance", payload.get("target_total_assets", self.settings.portfolio.initial_cash))),
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
            )
            with self.store.engine.begin() as connection:
                connection.execute(insert(self.store.accounts), self._account_record(account))
            return self.get_account(account_id)

        account = AccountBook(
            account_id=existing.account_id,
            base_currency=str(payload.get("base_currency", existing.base_currency)),
            target_total_assets=float(payload.get("target_total_assets", existing.target_total_assets)),
            cash_balance=float(payload.get("cash_balance", existing.cash_balance)),
            created_at=existing.created_at,
            updated_at=now.isoformat(),
        )
        with self.store.engine.begin() as connection:
            connection.execute(
                update(self.store.accounts)
                .where(self.store.accounts.c.account_id == account_id)
                .values(self._account_record(account)),
            )
        self._refresh_positions(account_id)
        return self.get_account(account_id)

    def list_positions(self, account_id: str = "default") -> dict[str, Any]:
        account_id = self._normalize_account_id(account_id)
        account = self._ensure_account(account_id)
        positions = self._positions(account_id, account.target_total_assets)
        return {
            "account_id": account_id,
            "updated_at": utcnow_iso(),
            "items": [asdict(item) for item in positions],
        }

    def list_trades(self, account_id: str = "default", limit: int = 50) -> dict[str, Any]:
        account_id = self._normalize_account_id(account_id)
        trades = self._trades(account_id)
        items = [asdict(item) for item in trades[-max(0, limit) :]][::-1]
        return {
            "account_id": account_id,
            "count": len(items),
            "items": items,
        }

    def create_manual_trade(self, payload: dict[str, Any], account_id: str = "default") -> dict[str, Any]:
        account_id = self._normalize_account_id(account_id)
        account = self._ensure_account(account_id)
        trade = self._trade_from_payload(payload, account_id=account_id, source="manual")
        next_account = apply_trade_to_account(account, trade)
        self._persist_trade_and_account(trade, next_account)
        positions = self._refresh_positions(account_id)
        pnl = summarize_account_pnl(
            initial_total_assets=next_account.target_total_assets,
            cash_balance=next_account.cash_balance,
            positions=positions,
            trades=self._trades(account_id),
        )
        return {
            "trade": asdict(trade),
            "account": asdict(next_account),
            "pnl": pnl,
            "positions": [asdict(item) for item in positions],
        }

    def apply_suggestion(self, suggestion_id: str, executed_price: float | None = None, account_id: str = "default") -> dict[str, Any]:
        account_id = self._normalize_account_id(account_id)
        account = self._ensure_account(account_id)
        suggestion = self._load_suggestion(suggestion_id)
        if suggestion is None:
            raise ValueError(f"Suggestion not found: {suggestion_id}")
        if bool(suggestion["blocked"]):
            raise ValueError("Blocked suggestion cannot be applied.")
        if bool(suggestion["applied"]):
            raise ValueError("Suggestion already applied.")

        symbol = str(suggestion["symbol"])
        price = float(executed_price or self.store.latest_nav(symbol) or 0.0)
        if price <= 0:
            raise ValueError(f"No valid executed price for suggestion: {symbol}")
        amount = abs(float(suggestion["delta_value"]))
        fund_name = self.store.latest_fund_name(symbol)
        side = "BUY" if float(suggestion["delta_value"]) >= 0 else "SELL"
        trade = self._trade_from_payload(
            {
                "symbol": symbol,
                "fund_name": fund_name,
                "side": side,
                "amount": amount,
                "price": price,
                "suggestion_id": str(suggestion["suggestion_id"]),
                "note": str(suggestion["reason"]),
            },
            account_id=account_id,
            source="suggestion_apply",
        )
        next_account = apply_trade_to_account(account, trade)
        self._persist_trade_and_account(trade, next_account)
        with self.store.engine.begin() as connection:
            connection.execute(
                update(self.store.rebalance_suggestions)
                .where(self.store.rebalance_suggestions.c.suggestion_id == int(suggestion_id))
                .values(applied=True, applied_trade_id=trade.trade_id)
            )
        positions = self._refresh_positions(account_id)
        pnl = summarize_account_pnl(
            initial_total_assets=next_account.target_total_assets,
            cash_balance=next_account.cash_balance,
            positions=positions,
            trades=self._trades(account_id),
        )
        return {
            "trade": asdict(trade),
            "account": asdict(next_account),
            "pnl": pnl,
            "positions": [asdict(item) for item in positions],
        }

    def to_portfolio_state(self, account_id: str = "default") -> PortfolioState:
        account_id = self._normalize_account_id(account_id)
        account = self._ensure_account(account_id)
        positions = self._positions(account_id, account.target_total_assets)
        return PortfolioState(
            cash=account.cash_balance,
            equity=account.target_total_assets,
            positions=[
                Position(
                    symbol=item.symbol,
                    shares=int(round(item.units)),
                    available_shares=int(round(item.units)),
                    market_value=item.market_value,
                    cost_basis=item.avg_cost,
                    category="UNKNOWN",
                    fund_type="UNKNOWN",
                    weight=item.weight,
                )
                for item in positions
            ],
        )

    def _ensure_account(self, account_id: str) -> AccountBook:
        account_id = self._normalize_account_id(account_id)
        existing = self._load_account(account_id)
        if existing is not None:
            return existing
        return AccountBook(
            account_id=account_id,
            base_currency=self.settings.account.base_currency,
            target_total_assets=self.settings.portfolio.initial_cash,
            cash_balance=self.settings.portfolio.initial_cash,
            created_at=utcnow_iso(),
            updated_at=utcnow_iso(),
        )

    def _normalize_account_id(self, account_id: str) -> str:
        return str(account_id).strip() or self.settings.account.default_account_id

    def _load_account(self, account_id: str) -> AccountBook | None:
        with self.store.engine.begin() as connection:
            row = connection.execute(
                select(self.store.accounts).where(self.store.accounts.c.account_id == account_id)
            ).mappings().first()
        if row is None:
            return None
        return AccountBook(
            account_id=str(row["account_id"]),
            base_currency=str(row["base_currency"]),
            target_total_assets=float(row["target_total_assets"]),
            cash_balance=float(row["cash_balance"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _positions(self, account_id: str, total_assets: float) -> list[PositionSnapshot]:
        trades = self._trades(account_id)
        symbols = [item.symbol for item in trades]
        nav_map = self.store.latest_nav_by_symbol(symbols)
        return rebuild_positions([], trades, nav_by_symbol=nav_map, total_assets=total_assets)

    def _refresh_positions(self, account_id: str) -> list[PositionSnapshot]:
        account = self._ensure_account(account_id)
        positions = self._positions(account_id, account.target_total_assets)
        now = _utcnow()
        with self.store.engine.begin() as connection:
            connection.execute(delete(self.store.position_snapshots).where(self.store.position_snapshots.c.account_id == account_id))
            if positions:
                connection.execute(insert(self.store.position_snapshots), [
                    {
                        "account_id": account_id,
                        "symbol": item.symbol,
                        "fund_name": item.fund_name,
                        "units": item.units,
                        "cost_basis": item.cost_value,
                        "average_cost": item.avg_cost,
                        "last_nav": item.last_nav,
                        "market_value": item.market_value,
                        "unrealized_pnl": item.unrealized_pnl,
                        "snapshot_at": now,
                        "applied_trade_id": "",
                    }
                    for item in positions
                ])
        return positions

    def _trades(self, account_id: str) -> list[LedgerTrade]:
        with self.store.engine.begin() as connection:
            rows = connection.execute(
                select(self.store.trade_ledger)
                .where(self.store.trade_ledger.c.account_id == account_id)
                .order_by(self.store.trade_ledger.c.trade_time.asc(), self.store.trade_ledger.c.created_at.asc())
            ).mappings().all()
        trades: list[LedgerTrade] = []
        for row in rows:
            trades.append(
                LedgerTrade(
                    trade_id=str(row["trade_id"]),
                    account_id=str(row["account_id"]),
                    symbol=str(row["symbol"]),
                    fund_name=str(row["fund_name"]),
                    side=str(row["side"]).upper(),  # type: ignore[arg-type]
                    amount=float(row["amount"]),
                    units=float(row["units"]),
                    price=float(row["price"]),
                    source=str(row["source"]),  # type: ignore[arg-type]
                    suggestion_id=str(row["suggestion_id"]),
                    note=str(row["note"]),
                    trade_time=row["trade_time"].isoformat() if hasattr(row["trade_time"], "isoformat") else str(row["trade_time"]),
                    created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                )
            )
        return trades

    def _persist_trade_and_account(self, trade: LedgerTrade, account: AccountBook) -> None:
        with self.store.engine.begin() as connection:
            connection.execute(insert(self.store.trade_ledger), self._trade_record(trade))
            if self._load_account(account.account_id) is None:
                connection.execute(insert(self.store.accounts), self._account_record(account))
            else:
                connection.execute(
                    update(self.store.accounts)
                    .where(self.store.accounts.c.account_id == account.account_id)
                    .values(self._account_record(account)),
                )

    def _load_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        with self.store.engine.begin() as connection:
            row = connection.execute(
                select(self.store.rebalance_suggestions).where(
                    self.store.rebalance_suggestions.c.suggestion_id == int(suggestion_id)
                )
            ).mappings().first()
        return dict(row) if row is not None else None

    @staticmethod
    def _account_record(account: AccountBook) -> dict[str, Any]:
        def _coerce(value: str) -> datetime:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        return {
            "account_id": account.account_id,
            "base_currency": account.base_currency,
            "target_total_assets": account.target_total_assets,
            "cash_balance": account.cash_balance,
            "created_at": _coerce(account.created_at or utcnow_iso()),
            "updated_at": _coerce(account.updated_at or utcnow_iso()),
        }

    def _trade_from_payload(self, payload: dict[str, Any], *, account_id: str, source: str) -> LedgerTrade:
        symbol = str(payload.get("symbol", "")).strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        side = str(payload.get("side", "BUY")).strip().upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError(f"Unsupported side: {side}")
        amount = float(payload.get("amount", 0.0))
        price = float(payload.get("price", payload.get("executed_price", 0.0)))
        units = float(payload.get("units", 0.0))
        if amount <= 0:
            raise ValueError("amount must be > 0")
        if price <= 0 and units <= 0:
            raise ValueError("price or units must be > 0")
        if units <= 0:
            units = amount / price
        if price <= 0:
            price = amount / units
        now = utcnow_iso()
        trade_side = cast(TradeSide, side)
        return LedgerTrade(
            trade_id=str(payload.get("trade_id", new_trade_id())),
            account_id=account_id,
            symbol=symbol,
            fund_name=str(payload.get("fund_name", symbol)).strip() or symbol,
            side=trade_side,
            amount=round(amount, 2),
            units=units,
            price=price,
            source=source,  # type: ignore[arg-type]
            suggestion_id=str(payload.get("suggestion_id", "")),
            note=str(payload.get("note", "")),
            trade_time=str(payload.get("trade_time", now)),
            created_at=now,
        )

    @staticmethod
    def _trade_record(trade: LedgerTrade) -> dict[str, Any]:
        def _coerce(value: str) -> datetime:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        return {
            "trade_id": trade.trade_id,
            "account_id": trade.account_id,
            "symbol": trade.symbol,
            "fund_name": trade.fund_name,
            "side": trade.side,
            "amount": trade.amount,
            "units": trade.units,
            "price": trade.price,
            "source": trade.source,
            "suggestion_id": trade.suggestion_id,
            "note": trade.note,
            "trade_time": _coerce(trade.trade_time or utcnow_iso()),
            "created_at": _coerce(trade.created_at or utcnow_iso()),
        }
