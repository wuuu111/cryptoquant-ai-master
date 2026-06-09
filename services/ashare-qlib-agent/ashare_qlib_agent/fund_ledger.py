from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


TradeSide = Literal["BUY", "SELL"]
TradeSource = Literal["manual", "suggestion_apply"]


@dataclass(frozen=True)
class AccountBook:
    account_id: str
    base_currency: str
    target_total_assets: float
    cash_balance: float
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class LedgerTrade:
    trade_id: str
    account_id: str
    symbol: str
    fund_name: str
    side: TradeSide
    amount: float
    units: float
    price: float
    source: TradeSource
    suggestion_id: str = ""
    note: str = ""
    trade_time: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    fund_name: str
    units: float
    avg_cost: float
    last_nav: float
    market_value: float
    cost_value: float
    weight: float
    unrealized_pnl: float
    unrealized_pnl_rate: float


def new_trade_id(prefix: str = "trade") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_trade_to_account(account: AccountBook, trade: LedgerTrade) -> AccountBook:
    cash_balance = account.cash_balance
    if trade.side == "BUY":
        cash_balance -= trade.amount
    else:
        cash_balance += trade.amount
    return AccountBook(
        account_id=account.account_id,
        base_currency=account.base_currency,
        target_total_assets=account.target_total_assets,
        cash_balance=round(cash_balance, 2),
        created_at=account.created_at,
        updated_at=trade.created_at or trade.trade_time or utcnow_iso(),
    )


def rebuild_positions(
    existing_positions: list[PositionSnapshot],
    trades: list[LedgerTrade],
    *,
    nav_by_symbol: dict[str, float],
    total_assets: float = 0.0,
) -> list[PositionSnapshot]:
    state: dict[str, dict[str, float | str]] = {
        item.symbol: {
            "symbol": item.symbol,
            "fund_name": item.fund_name,
            "units": item.units,
            "avg_cost": item.avg_cost,
        }
        for item in existing_positions
    }

    for trade in trades:
        row = state.get(
            trade.symbol,
            {
                "symbol": trade.symbol,
                "fund_name": trade.fund_name,
                "units": 0.0,
                "avg_cost": 0.0,
            },
        )
        current_units = float(row["units"])
        avg_cost = float(row["avg_cost"])
        if trade.side == "BUY":
            next_units = current_units + trade.units
            next_cost = (current_units * avg_cost) + trade.amount
            row["units"] = next_units
            row["avg_cost"] = next_cost / next_units if next_units > 0 else 0.0
            row["fund_name"] = trade.fund_name or str(row["fund_name"])
            state[trade.symbol] = row
            continue

        next_units = max(0.0, current_units - trade.units)
        if next_units <= 1e-9:
            state.pop(trade.symbol, None)
            continue
        row["units"] = next_units
        state[trade.symbol] = row

    positions: list[PositionSnapshot] = []
    for symbol, row in sorted(state.items(), key=lambda item: item[0]):
        units = float(row["units"])
        if units <= 1e-9:
            continue
        last_nav = float(nav_by_symbol.get(symbol, row["avg_cost"] or 0.0))
        market_value = units * last_nav
        cost_value = units * float(row["avg_cost"])
        unrealized_pnl = market_value - cost_value
        weight = market_value / total_assets if total_assets > 0 else 0.0
        positions.append(
            PositionSnapshot(
                symbol=symbol,
                fund_name=str(row["fund_name"]),
                units=units,
                avg_cost=float(row["avg_cost"]),
                last_nav=last_nav,
                market_value=round(market_value, 2),
                cost_value=round(cost_value, 2),
                weight=weight,
                unrealized_pnl=round(unrealized_pnl, 2),
                unrealized_pnl_rate=(unrealized_pnl / cost_value) if cost_value > 0 else 0.0,
            )
        )
    return positions


def summarize_account_pnl(
    *,
    initial_total_assets: float,
    cash_balance: float,
    positions: list[PositionSnapshot],
    trades: list[LedgerTrade],
) -> dict[str, float]:
    open_costs: dict[str, tuple[float, float]] = {}
    realized_pnl = 0.0

    for trade in trades:
        units, total_cost = open_costs.get(trade.symbol, (0.0, 0.0))
        if trade.side == "BUY":
            open_costs[trade.symbol] = (units + trade.units, total_cost + trade.amount)
            continue
        avg_cost = (total_cost / units) if units > 0 else 0.0
        realized_pnl += trade.amount - (avg_cost * trade.units)
        next_units = max(0.0, units - trade.units)
        next_cost = max(0.0, total_cost - (avg_cost * trade.units))
        if next_units <= 1e-9:
            open_costs.pop(trade.symbol, None)
        else:
            open_costs[trade.symbol] = (next_units, next_cost)

    market_value = sum(item.market_value for item in positions)
    unrealized_pnl = sum(item.unrealized_pnl for item in positions)
    current_total_assets = round(cash_balance + market_value, 2)
    total_return = round(current_total_assets - initial_total_assets, 2)
    total_return_rate = (total_return / initial_total_assets) if initial_total_assets > 0 else 0.0

    return {
        "initial_total_assets": round(initial_total_assets, 2),
        "cash_balance": round(cash_balance, 2),
        "market_value": round(market_value, 2),
        "current_total_assets": current_total_assets,
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "total_pnl": total_return,
        "total_return": total_return,
        "total_return_rate": total_return_rate,
    }
