from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class PortfolioSettings:
    initial_cash: float = 1_000_000.0
    fee_rate: float = 0.0005
    max_position_weight: float = 0.20
    cash_reserve_weight: float = 0.05


@dataclass(frozen=True)
class FundDataSettings:
    source: str = "akshare"
    fund_pool_file: str = "fund_pool.csv"
    fund_nav_file: str = "fund_nav_daily.csv"
    fund_metadata_file: str = "fund_metadata.csv"
    benchmark_file: str = "benchmark_index.csv"
    portfolio_mode: str = "balanced"
    stale_nav_days: int = 5
    benchmark_index_code: str = "BENCH"
    reference_date: str = ""
    fund_codes: list[str] = field(default_factory=list)
    fund_type_keywords: list[str] = field(
        default_factory=lambda: ["ETF", "LOF", "指数", "债券", "货币", "QDII", "商品", "混合"]
    )
    max_funds: int = 40


@dataclass(frozen=True)
class DatabaseSettings:
    enabled: bool = False
    url: str = ""
    schema: str = "public"
    mirror_csv: bool = True
    save_cycles: bool = True


@dataclass(frozen=True)
class AccountSettings:
    default_account_id: str = "default"
    base_currency: str = "CNY"


@dataclass(frozen=True)
class FundGraphSettings:
    enabled: bool = True
    llm_enabled: bool = True
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_timeout: float = 8.0
    llm_retries: int = 0


@dataclass(frozen=True)
class SchedulerSettings:
    enabled: bool = False
    interval_minutes: int = 1440
    run_on_startup: bool = True
    sync_before_cycle: bool = True
    portfolio_file: str = ""
    start_date: str = ""
    end_date: str = ""


@dataclass(frozen=True)
class RuntimeSettings:
    data_dir: Path = Path("./data")
    registry_dir: Path = Path("./registry")
    provider: str = "akshare"
    fetch_workers: int = 1
    start_date: str = "20230101"
    end_date: str = ""
    portfolio: PortfolioSettings = field(default_factory=PortfolioSettings)
    fund_data: FundDataSettings = field(default_factory=FundDataSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    account: AccountSettings = field(default_factory=AccountSettings)
    fund_graph: FundGraphSettings = field(default_factory=FundGraphSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RuntimeSettings":
        if path is None:
            return cls()
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        raw = _load_yaml(config_path)
        raw = _resolve_env_placeholders(raw)
        portfolio = PortfolioSettings(**{**PortfolioSettings().__dict__, **dict(raw.get("portfolio", {}))})
        fund_data = FundDataSettings(**{**FundDataSettings().__dict__, **dict(raw.get("fund_data", {}))})
        database = DatabaseSettings(**{**DatabaseSettings().__dict__, **dict(raw.get("database", {}))})
        account = AccountSettings(**{**AccountSettings().__dict__, **dict(raw.get("account", {}))})
        fund_graph = FundGraphSettings(**{**FundGraphSettings().__dict__, **dict(raw.get("fund_graph", {}))})
        scheduler = SchedulerSettings(**{**SchedulerSettings().__dict__, **dict(raw.get("scheduler", {}))})
        return cls(
            data_dir=Path(raw.get("data_dir", "./data")),
            registry_dir=Path(raw.get("registry_dir", "./registry")),
            provider=str(raw.get("provider", "akshare")),
            fetch_workers=int(raw.get("fetch_workers", 1)),
            start_date=str(raw.get("start_date", "20230101")),
            end_date=str(raw.get("end_date", "")),
            portfolio=portfolio,
            fund_data=fund_data,
            database=database,
            account=account,
            fund_graph=fund_graph,
            scheduler=scheduler,
        )

    def ensure_dirs(self) -> None:
        for path in [
            self.data_dir,
            self.data_dir / "raw",
            self.data_dir / "features",
            self.registry_dir,
            self.registry_dir / "reports",
            Path("./orders"),
        ]:
            path.mkdir(parents=True, exist_ok=True)


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a YAML object: {path}")
    return data


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]
    if isinstance(value, str):
        return _ENV_PATTERN.sub(_replace_env_match, value)
    return value


def _replace_env_match(match: re.Match[str]) -> str:
    name = match.group(1)
    default = match.group(2)
    return os.environ.get(name, default or "")
