from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .fund_store import FundStore, database_enabled
from .settings import DatabaseSettings, FundDataSettings


@dataclass(frozen=True)
class FundSyncReport:
    fund_count: int
    nav_rows: int
    benchmark_rows: int
    as_of: str
    files: list[str]
    skipped: list[dict[str, str]] = field(default_factory=list)


class AkshareFundDataSource:
    def fund_catalog(self) -> pd.DataFrame:
        import akshare as ak

        return ak.fund_name_em()

    def open_fund_daily(self) -> pd.DataFrame:
        import akshare as ak

        return ak.fund_open_fund_daily_em()

    def etf_fund_daily(self) -> pd.DataFrame:
        import akshare as ak

        return ak.fund_etf_fund_daily_em()

    def purchase_status(self) -> pd.DataFrame:
        import akshare as ak

        return ak.fund_purchase_em()

    def open_fund_nav(self, fund_code: str) -> pd.DataFrame:
        import akshare as ak

        return ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势", period="成立来")

    def etf_fund_nav(self, fund_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        import akshare as ak

        return ak.fund_etf_fund_info_em(fund=fund_code, start_date=start_date, end_date=end_date)

    def lof_fund_hist(self, fund_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        import akshare as ak

        return ak.fund_lof_hist_em(symbol=fund_code, period="daily", start_date=start_date, end_date=end_date, adjust="")

    def benchmark_hist(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        import akshare as ak

        try:
            return ak.index_zh_a_hist(symbol=index_code, period="daily", start_date=start_date, end_date=end_date)
        except Exception:
            symbol = _benchmark_symbol(index_code)
            try:
                return ak.stock_zh_index_daily(symbol=symbol)
            except Exception:
                return ak.stock_zh_index_daily_em(symbol=symbol, start_date=start_date, end_date=end_date)


class FundDataSyncer:
    def __init__(
        self,
        data_dir: Path,
        settings: FundDataSettings,
        source: AkshareFundDataSource | None = None,
        database: DatabaseSettings | None = None,
    ):
        self.data_dir = data_dir
        self.settings = settings
        self.source = source or AkshareFundDataSource()
        self.database = database or DatabaseSettings()

    def sync(self, start_date: str, end_date: str = "") -> FundSyncReport:
        final_end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")

        catalog = self._normalize_catalog(self.source.fund_catalog())
        purchase = self._normalize_purchase(self.source.purchase_status())
        open_daily = self._normalize_open_daily(self.source.open_fund_daily())
        etf_daily = self._normalize_etf_daily(self.source.etf_fund_daily())
        selected = self._select_funds(catalog, open_daily, etf_daily)

        pool_rows: list[dict[str, object]] = []
        meta_rows: list[dict[str, object]] = []
        nav_frames: list[pd.DataFrame] = []
        skipped: list[dict[str, str]] = []

        purchase_by_code = purchase.set_index("fund_code").to_dict("index") if not purchase.empty else {}
        open_by_code = open_daily.set_index("fund_code").to_dict("index") if not open_daily.empty else {}
        etf_by_code = etf_daily.set_index("fund_code").to_dict("index") if not etf_daily.empty else {}

        for row in selected.to_dict("records"):
            fund_code = str(row["fund_code"])
            fund_name = str(row["fund_name"])
            fund_type = str(row["fund_type"])
            try:
                nav_frame = self._fetch_nav_history(fund_code, fund_type, start_date, final_end_date)
            except Exception as error:
                skipped.append({"fund_code": fund_code, "reason": str(error)[:240]})
                continue
            if nav_frame.empty:
                skipped.append({"fund_code": fund_code, "reason": "empty history"})
                continue

            purchase_row = purchase_by_code.get(fund_code, {})
            open_row = open_by_code.get(fund_code, {})
            etf_row = etf_by_code.get(fund_code, {})
            category = _category_from_type(fund_type, fund_name)
            risk_level = _risk_level_from_category(category)
            tracking_index = _tracking_index_from_name(fund_name, fund_type)

            pool_rows.append(
                {
                    "fund_code": fund_code,
                    "fund_name": fund_name,
                    "category": category,
                    "fund_type": fund_type,
                    "tracking_index": tracking_index,
                    "risk_level": risk_level,
                    "enabled": 1,
                }
            )
            fee_value = purchase_row.get("fee", open_row.get("fee", etf_row.get("fee", 0.0)))
            meta_rows.append(
                {
                    "fund_code": fund_code,
                    "fund_name": fund_name,
                    "category": category,
                    "fund_type": fund_type,
                    "fee": float(fee_value or 0.0),
                    "aum": float(etf_row.get("aum", 0.0) or 0.0),
                    "manager": str(etf_row.get("manager", "")),
                    "purchase_status": str(purchase_row.get("purchase_status", open_row.get("purchase_status", "open")) or "open"),
                    "redemption_status": str(purchase_row.get("redemption_status", open_row.get("redemption_status", "open")) or "open"),
                }
            )
            nav_frames.append(nav_frame)

        if not nav_frames:
            raise RuntimeError("No fund history could be fetched from AkShare.")

        pool_frame = pd.DataFrame(pool_rows).drop_duplicates(subset=["fund_code"]).sort_values("fund_code")
        meta_frame = pd.DataFrame(meta_rows).drop_duplicates(subset=["fund_code"]).sort_values("fund_code")
        nav_frame = pd.concat(nav_frames, ignore_index=True).sort_values(["fund_code", "date"]).reset_index(drop=True)
        benchmark_frame = self._normalize_benchmark(
            self.source.benchmark_hist(self.settings.benchmark_index_code, start_date, final_end_date),
            self.settings.benchmark_index_code,
        )

        latest_date = pd.to_datetime(nav_frame["date"]).max()
        as_of = str(latest_date.date()) if pd.notna(latest_date) else ""
        files: list[str] = []
        if self.database.mirror_csv or not database_enabled(self.database):
            self.data_dir.mkdir(parents=True, exist_ok=True)
            pool_path = self.data_dir / self.settings.fund_pool_file
            meta_path = self.data_dir / self.settings.fund_metadata_file
            nav_path = self.data_dir / self.settings.fund_nav_file
            benchmark_path = self.data_dir / self.settings.benchmark_file
            pool_frame.to_csv(pool_path, index=False)
            meta_frame.to_csv(meta_path, index=False)
            nav_frame.to_csv(nav_path, index=False)
            benchmark_frame.to_csv(benchmark_path, index=False)
            files = [str(pool_path), str(nav_path), str(meta_path), str(benchmark_path)]
        report = FundSyncReport(
            fund_count=int(pool_frame["fund_code"].nunique()),
            nav_rows=int(len(nav_frame)),
            benchmark_rows=int(len(benchmark_frame)),
            as_of=as_of,
            files=files,
            skipped=skipped,
        )
        if database_enabled(self.database):
            store = FundStore(self.database.url, schema=self.database.schema)
            store.init_schema()
            store.write_sync_data(
                fund_pool=pool_frame,
                fund_nav=nav_frame,
                fund_metadata=meta_frame,
                benchmark=benchmark_frame,
                report=report.__dict__,
            )
        return report

    def _select_funds(self, catalog: pd.DataFrame, open_daily: pd.DataFrame, etf_daily: pd.DataFrame) -> pd.DataFrame:
        if self.settings.fund_codes:
            desired = {str(code).strip().upper() for code in self.settings.fund_codes}
            frame = catalog[catalog["fund_code"].isin(desired)].copy()
        else:
            frame = catalog.copy()
            keywords = [keyword.strip() for keyword in self.settings.fund_type_keywords if keyword.strip()]
            if keywords:
                frame = frame[frame["fund_type"].apply(lambda value: any(keyword in value for keyword in keywords))]
            eligible_codes = set(open_daily["fund_code"]) | set(etf_daily["fund_code"])
            if eligible_codes:
                frame = frame[frame["fund_code"].isin(eligible_codes)]
            if self.settings.max_funds > 0:
                frame = frame.head(self.settings.max_funds)
        return frame.drop_duplicates(subset=["fund_code"]).reset_index(drop=True)

    def _fetch_nav_history(self, fund_code: str, fund_type: str, start_date: str, end_date: str) -> pd.DataFrame:
        normalized_type = fund_type.upper()
        if "ETF" in normalized_type:
            frame = self.source.etf_fund_nav(fund_code, start_date, end_date)
            return self._normalize_etf_nav(frame, fund_code)
        if "LOF" in normalized_type:
            frame = self.source.lof_fund_hist(fund_code, start_date, end_date)
            return self._normalize_lof_hist(frame, fund_code)
        frame = self.source.open_fund_nav(fund_code)
        return self._normalize_open_nav(frame, fund_code, start_date, end_date)

    @staticmethod
    def _normalize_catalog(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.rename(
            columns={
                "基金代码": "fund_code",
                "基金简称": "fund_name",
                "基金类型": "fund_type",
            }
        )[["fund_code", "fund_name", "fund_type"]].copy()
        result["fund_code"] = result["fund_code"].astype(str).str.strip().str.upper()
        result["fund_name"] = result["fund_name"].astype(str).str.strip()
        result["fund_type"] = result["fund_type"].astype(str).str.strip()
        return result.drop_duplicates(subset=["fund_code"]).reset_index(drop=True)

    @staticmethod
    def _normalize_purchase(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.rename(
            columns={
                "基金代码": "fund_code",
                "基金简称": "fund_name",
                "基金类型": "fund_type",
                "申购状态": "purchase_status",
                "赎回状态": "redemption_status",
                "手续费": "fee",
            }
        ).copy()
        keep = ["fund_code", "fund_name", "fund_type", "purchase_status", "redemption_status", "fee"]
        result = result[[column for column in keep if column in result.columns]]
        result["fund_code"] = result["fund_code"].astype(str).str.strip().str.upper()
        fee_series = result["fee"] if "fee" in result.columns else pd.Series(0.0, index=result.index)
        result["fee"] = pd.to_numeric(fee_series, errors="coerce").fillna(0.0)
        return result.drop_duplicates(subset=["fund_code"]).reset_index(drop=True)

    @staticmethod
    def _normalize_open_daily(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.rename(
            columns={
                "基金代码": "fund_code",
                "基金简称": "fund_name",
                "申购状态": "purchase_status",
                "赎回状态": "redemption_status",
                "手续费": "fee",
            }
        ).copy()
        keep = ["fund_code", "fund_name", "purchase_status", "redemption_status", "fee"]
        result = result[[column for column in keep if column in result.columns]]
        result["fund_code"] = result["fund_code"].astype(str).str.strip().str.upper()
        fee_series = result["fee"] if "fee" in result.columns else pd.Series(0.0, index=result.index)
        result["fee"] = pd.to_numeric(fee_series, errors="coerce").fillna(0.0)
        return result.drop_duplicates(subset=["fund_code"]).reset_index(drop=True)

    @staticmethod
    def _normalize_etf_daily(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.rename(
            columns={
                "基金代码": "fund_code",
                "基金简称": "fund_name",
                "类型": "fund_type",
            }
        ).copy()
        keep = ["fund_code", "fund_name", "fund_type"]
        result = result[[column for column in keep if column in result.columns]]
        result["fund_code"] = result["fund_code"].astype(str).str.strip().str.upper()
        result["fund_type"] = result["fund_type"].astype(str).str.strip()
        result["aum"] = 0.0
        result["manager"] = ""
        result["fee"] = 0.0
        return result.drop_duplicates(subset=["fund_code"]).reset_index(drop=True)

    @staticmethod
    def _normalize_open_nav(frame: pd.DataFrame, fund_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["date", "fund_code", "nav", "daily_return"])
        result = frame.rename(
            columns={"净值日期": "date", "单位净值": "nav", "日增长率": "daily_return"}
        )[["date", "nav", "daily_return"]].copy()
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        result = result.dropna(subset=["date"])
        result = result[(result["date"] >= pd.to_datetime(start_date)) & (result["date"] <= pd.to_datetime(end_date))]
        result["nav"] = pd.to_numeric(result["nav"], errors="coerce")
        result["daily_return"] = pd.to_numeric(result["daily_return"], errors="coerce") / 100.0
        result["daily_return"] = result["daily_return"].fillna(result["nav"].pct_change().fillna(0.0))
        result["fund_code"] = fund_code
        return result[["date", "fund_code", "nav", "daily_return"]].dropna(subset=["nav"]).reset_index(drop=True)

    @staticmethod
    def _normalize_etf_nav(frame: pd.DataFrame, fund_code: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["date", "fund_code", "nav", "daily_return"])
        result = frame.rename(
            columns={"净值日期": "date", "单位净值": "nav", "日增长率": "daily_return"}
        )[["date", "nav", "daily_return"]].copy()
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        result["nav"] = pd.to_numeric(result["nav"], errors="coerce")
        result["daily_return"] = pd.to_numeric(result["daily_return"], errors="coerce") / 100.0
        result["daily_return"] = result["daily_return"].fillna(result["nav"].pct_change().fillna(0.0))
        result["fund_code"] = fund_code
        return result[["date", "fund_code", "nav", "daily_return"]].dropna(subset=["date", "nav"]).reset_index(drop=True)

    @staticmethod
    def _normalize_lof_hist(frame: pd.DataFrame, fund_code: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["date", "fund_code", "nav", "daily_return"])
        result = frame.rename(columns={"日期": "date", "收盘": "nav", "涨跌幅": "daily_return"})[
            ["date", "nav", "daily_return"]
        ].copy()
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        result["nav"] = pd.to_numeric(result["nav"], errors="coerce")
        result["daily_return"] = pd.to_numeric(result["daily_return"], errors="coerce") / 100.0
        result["daily_return"] = result["daily_return"].fillna(result["nav"].pct_change().fillna(0.0))
        result["fund_code"] = fund_code
        return result[["date", "fund_code", "nav", "daily_return"]].dropna(subset=["date", "nav"]).reset_index(drop=True)

    @staticmethod
    def _normalize_benchmark(frame: pd.DataFrame, index_code: str) -> pd.DataFrame:
        rename_map = {"日期": "date", "date": "date", "收盘": "close", "close": "close", "涨跌幅": "daily_return"}
        result = frame.rename(columns=rename_map).copy()
        if "date" not in result.columns or "close" not in result.columns:
            raise ValueError("benchmark history missing required date/close columns")
        keep = ["date", "close"] + (["daily_return"] if "daily_return" in result.columns else [])
        result = result[keep].copy()
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        result["close"] = pd.to_numeric(result["close"], errors="coerce")
        daily_return = result["daily_return"] if "daily_return" in result.columns else pd.Series(index=result.index, dtype=float)
        result["daily_return"] = pd.to_numeric(daily_return, errors="coerce") / 100.0
        result["daily_return"] = result["daily_return"].fillna(result["close"].pct_change().fillna(0.0))
        result["index_code"] = index_code.upper()
        return result[["date", "index_code", "close", "daily_return"]].dropna(subset=["date", "close"]).reset_index(drop=True)


def _category_from_type(fund_type: str, fund_name: str = "") -> str:
    value = f"{fund_type.strip()} {fund_name.strip()}".lower()
    if "货币" in value:
        return "cash"
    if any(keyword in value for keyword in ("债", "固收", "国债", "可转债")):
        return "bond"
    if any(keyword in value for keyword in ("qdii", "海外", "纳指", "标普", "恒生", "日经", "美股", "港股")):
        return "qdii"
    if any(keyword in value for keyword in ("商品", "黄金", "原油", "gold")):
        return "commodity"
    if "lof" in value or "etf" in value or "指数" in value or "股票" in value or "混合" in value:
        return "equity"
    return "equity"


def _risk_level_from_category(category: str) -> str:
    if category in {"bond", "cash"}:
        return "low"
    if category == "commodity":
        return "medium"
    return "high"


def _tracking_index_from_name(fund_name: str, fund_type: str) -> str:
    if "指数" in fund_type or "ETF" in fund_type.upper():
        return fund_name
    return ""


def _benchmark_symbol(index_code: str) -> str:
    code = index_code.strip().lower()
    if code.startswith(("sh", "sz")):
        return code
    if code.startswith("0") or code.startswith("5") or code.startswith("6"):
        return f"sh{code}"
    return f"sz{code}"
