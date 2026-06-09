from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ashare_qlib_agent.fund_fixtures import write_sample_fund_data
from ashare_qlib_agent.fund_account_service import FundAccountService
from ashare_qlib_agent.fund_live_cycle import cycle_from_settings, feature_snapshot_from_settings, latest_cycle_from_store
from ashare_qlib_agent.fund_scheduler import FundTaskScheduler
from ashare_qlib_agent.fund_store import FundStore, database_enabled
from ashare_qlib_agent.fund_sync import FundDataSyncer
from ashare_qlib_agent.llm import LLMClient
from ashare_qlib_agent.schemas import parse_portfolio
from ashare_qlib_agent.settings import RuntimeSettings


class FundCycleRequest(BaseModel):
    config_path: str = Field(default="")
    portfolio: dict = Field(default_factory=dict)


class SyncFundRequest(BaseModel):
    config_path: str = Field(default="")
    start_date: str = Field(default="")
    end_date: str = Field(default="")


class SampleFundRequest(BaseModel):
    config_path: str = Field(default="")
    days: int = Field(default=180)
    end_date: str = Field(default="")


class ManualHolding(BaseModel):
    symbol: str = Field(default="")
    name: str = Field(default="")
    quantity: float = Field(default=0)
    cost_price: float = Field(default=0)
    last_price: float = Field(default=0)
    note: str = Field(default="")
    updated_at: str = Field(default="")


class ManualHoldingBook(BaseModel):
    holdings: list[ManualHolding] = Field(default_factory=list)


class AccountPayload(BaseModel):
    account_id: str = Field(default="default")
    base_currency: str = Field(default="CNY")
    target_total_assets: float = Field(default=0)
    cash_balance: float = Field(default=0)


class ManualTradePayload(BaseModel):
    account_id: str = Field(default="default")
    symbol: str = Field(default="")
    fund_name: str = Field(default="")
    side: str = Field(default="BUY")
    amount: float = Field(default=0)
    price: float = Field(default=0)
    units: float = Field(default=0)
    note: str = Field(default="")
    trade_time: str = Field(default="")


class ApplySuggestionPayload(BaseModel):
    account_id: str = Field(default="default")
    executed_price: float = Field(default=0)


app = FastAPI(title="Fund Rotation Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_scheduler: FundTaskScheduler | None = None


@app.get("/")
def index() -> dict:
    return {
        "name": "Fund Rotation Agent",
        "ok": True,
        "endpoints": {
            "health": "GET /health",
            "fund_features": "GET /fund-features",
            "holdings": "GET/POST /holdings",
            "account": "GET/POST /account",
            "positions": "GET /positions",
            "trades": "GET/POST /trades",
            "fund_cycle": "POST /fund-cycle",
            "sync_fund_data": "POST /sync-fund-data",
            "sample_fund_data": "POST /sample-fund-data",
        },
    }


@app.get("/health")
def health() -> dict:
    settings = _load_settings()
    llm = LLMClient.from_settings(settings)
    payload = {
        "ok": True,
        "service": "fund_rotation_agent",
        "database_enabled": database_enabled(settings.database),
        "scheduler_enabled": settings.scheduler.enabled,
        "llm": {
            "enabled": llm.enabled,
            "model": llm.model,
            "base_url": llm.base_url,
            "status": llm.status,
        },
    }
    if database_enabled(settings.database):
        payload["database"] = FundStore.from_settings(settings).status().__dict__
    return payload


@app.get("/fund-features")
def fund_features(config_path: str = "", limit: int = 20) -> dict:
    settings = _load_settings(config_path)
    return feature_snapshot_from_settings(settings, limit=max(0, limit))


@app.post("/fund-cycle")
def fund_cycle(request: FundCycleRequest) -> dict:
    settings = _load_settings(request.config_path)
    portfolio = parse_portfolio(request.portfolio)
    if portfolio.cash <= 0 and portfolio.equity <= 0 and not portfolio.positions:
        return cycle_from_settings(settings)
    return cycle_from_settings(settings, portfolio)


@app.get("/latest-cycle")
def latest_cycle(config_path: str = "") -> dict:
    settings = _load_settings(config_path)
    return latest_cycle_from_store(settings) or {}


@app.post("/sync-fund-data")
def sync_fund_data(request: SyncFundRequest) -> dict:
    settings = _load_settings(request.config_path)
    report = FundDataSyncer(settings.data_dir, settings.fund_data, database=settings.database).sync(
        start_date=request.start_date or settings.start_date,
        end_date=request.end_date or settings.end_date,
    )
    return report.__dict__


@app.post("/sample-fund-data")
def sample_fund_data(request: SampleFundRequest) -> dict:
    settings = _load_settings(request.config_path)
    return write_sample_fund_data(
        settings.data_dir,
        periods=max(60, int(request.days)),
        end_date=request.end_date or None,
    )


@app.post("/scheduler/run-once")
def scheduler_run_once(config_path: str = "", account_id: str = "default") -> dict:
    settings = _load_settings(config_path)
    return FundTaskScheduler(settings, account_id=account_id).run_once().__dict__


@app.get("/holdings")
def get_holdings() -> dict:
    return _read_holdings()


@app.post("/holdings")
def save_holdings(book: ManualHoldingBook) -> dict:
    path = _holdings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for item in book.holdings:
        row = item.model_dump()
        row["symbol"] = row["symbol"].strip().upper()
        row["name"] = row["name"].strip()
        row["note"] = row["note"].strip()
        row["updated_at"] = now
        if row["symbol"]:
            rows.append(row)
    payload = {"updated_at": now, "holdings": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


@app.get("/account")
def get_account(account_id: str = "default", config_path: str = "") -> dict:
    return _account_service(config_path).get_account(account_id=account_id)


@app.post("/account")
def save_account(payload: AccountPayload, config_path: str = "") -> dict:
    return _account_service(config_path).upsert_account(payload.model_dump())


@app.get("/positions")
def get_positions(account_id: str = "default", config_path: str = "") -> dict:
    return _account_service(config_path).list_positions(account_id=account_id)


@app.get("/trades")
def get_trades(account_id: str = "default", limit: int = 50, config_path: str = "") -> dict:
    return _account_service(config_path).list_trades(account_id=account_id, limit=limit)


@app.post("/trades")
def create_trade(payload: ManualTradePayload, config_path: str = "") -> dict:
    return _account_service(config_path).create_manual_trade(payload.model_dump(), account_id=payload.account_id)


@app.post("/suggestions/{suggestion_id}/apply")
def apply_suggestion(suggestion_id: str, payload: ApplySuggestionPayload, config_path: str = "") -> dict:
    return _account_service(config_path).apply_suggestion(
        suggestion_id,
        executed_price=payload.executed_price or None,
        account_id=payload.account_id,
    )


def _holdings_path() -> Path:
    return Path("orders") / "manual_holdings.json"


def _read_holdings() -> dict:
    path = _holdings_path()
    if not path.exists():
        return {"updated_at": "", "holdings": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _default_config_path() -> str:
    return os.environ.get("FUND_AGENT_CONFIG", "config.real-local.yaml")


def _load_settings(config_path: str = "") -> RuntimeSettings:
    return RuntimeSettings.load(config_path or _default_config_path())


def _account_service(config_path: str = "") -> FundAccountService:
    return FundAccountService.from_settings(_load_settings(config_path))


@app.on_event("startup")
def _startup_scheduler() -> None:
    global _scheduler
    settings = _load_settings()
    if settings.scheduler.enabled:
        _scheduler = FundTaskScheduler(settings)
        _scheduler.start()


@app.on_event("shutdown")
def _shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.stop()
        _scheduler = None
