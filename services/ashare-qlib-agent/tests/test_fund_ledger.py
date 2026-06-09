from ashare_qlib_agent.fund_ledger import (
    AccountBook,
    LedgerTrade,
    apply_trade_to_account,
    rebuild_positions,
    summarize_account_pnl,
)
from ashare_qlib_agent.fund_store import FundStore


def test_buy_trade_reduces_cash_and_creates_position():
    account = AccountBook(
        account_id="default",
        base_currency="CNY",
        target_total_assets=1_000_000.0,
        cash_balance=1_000_000.0,
    )
    trade = LedgerTrade(
        trade_id="t1",
        account_id="default",
        symbol="000001",
        fund_name="华夏成长混合",
        side="BUY",
        amount=80_000.0,
        units=60_240.9639,
        price=1.3280,
        source="manual",
    )

    next_account = apply_trade_to_account(account, trade)
    positions = rebuild_positions([], [trade], nav_by_symbol={"000001": 1.3280}, total_assets=1_000_000.0)

    assert next_account.cash_balance == 920_000.0
    assert positions[0].symbol == "000001"
    assert round(positions[0].market_value, 2) == 80_000.0
    assert round(positions[0].weight, 4) == 0.08


def test_sell_trade_realizes_profit_and_increases_cash():
    account = AccountBook(
        account_id="default",
        base_currency="CNY",
        target_total_assets=1_000_000.0,
        cash_balance=1_000_000.0,
    )
    buy = LedgerTrade(
        trade_id="buy1",
        account_id="default",
        symbol="000001",
        fund_name="华夏成长混合",
        side="BUY",
        amount=80_000.0,
        units=60_240.9639,
        price=1.3280,
        source="manual",
    )
    sell = LedgerTrade(
        trade_id="sell1",
        account_id="default",
        symbol="000001",
        fund_name="华夏成长混合",
        side="SELL",
        amount=90_000.0,
        units=60_240.9639,
        price=1.4940,
        source="manual",
    )

    account = apply_trade_to_account(account, buy)
    account = apply_trade_to_account(account, sell)
    positions = rebuild_positions([], [buy, sell], nav_by_symbol={"000001": 1.4940}, total_assets=1_010_000.0)
    pnl = summarize_account_pnl(
        initial_total_assets=1_000_000.0,
        cash_balance=account.cash_balance,
        positions=positions,
        trades=[buy, sell],
    )

    assert positions == []
    assert pnl["realized_pnl"] > 0
    assert pnl["current_total_assets"] == 1_010_000.0
    assert pnl["total_return"] == 10_000.0


def test_pnl_summary_includes_unrealized_value_from_open_positions():
    trade = LedgerTrade(
        trade_id="buy1",
        account_id="default",
        symbol="000001",
        fund_name="华夏成长混合",
        side="BUY",
        amount=80_000.0,
        units=60_240.9639,
        price=1.3280,
        source="manual",
    )

    positions = rebuild_positions([], [trade], nav_by_symbol={"000001": 1.4000}, total_assets=1_004_337.35)
    pnl = summarize_account_pnl(
        initial_total_assets=1_000_000.0,
        cash_balance=920_000.0,
        positions=positions,
        trades=[trade],
    )

    assert round(pnl["current_total_assets"], 2) == 1_004_337.35
    assert round(pnl["unrealized_pnl"], 2) == 4_337.35
    assert round(pnl["total_return"], 2) == 4_337.35


def test_fund_store_exposes_unified_ledger_tables():
    store = FundStore("sqlite:///:memory:", schema="")
    store.init_schema()

    assert store.accounts.name == "fund_accounts"
    assert store.trade_ledger.name == "fund_trade_ledger"
    assert store.position_snapshots.name == "fund_positions"
