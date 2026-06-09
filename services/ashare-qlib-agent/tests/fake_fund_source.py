import pandas as pd


class FakeFundDataSource:
    def fund_catalog(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"基金代码": "ETF001", "基金简称": "Core ETF", "基金类型": "ETF-指数"},
                {"基金代码": "BOND01", "基金简称": "Bond Plus", "基金类型": "债券型-长债"},
                {"基金代码": "LOF001", "基金简称": "Growth LOF", "基金类型": "LOF"},
            ]
        )

    def open_fund_daily(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"基金代码": "BOND01", "基金简称": "Bond Plus", "申购状态": "开放申购", "赎回状态": "开放赎回", "手续费": 0.3},
            ]
        )

    def etf_fund_daily(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"基金代码": "ETF001", "基金简称": "Core ETF", "类型": "ETF-指数"},
                {"基金代码": "LOF001", "基金简称": "Growth LOF", "类型": "LOF"},
            ]
        )

    def purchase_status(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"基金代码": "ETF001", "基金简称": "Core ETF", "基金类型": "ETF-指数", "申购状态": "开放申购", "赎回状态": "开放赎回", "手续费": 0.5},
                {"基金代码": "BOND01", "基金简称": "Bond Plus", "基金类型": "债券型-长债", "申购状态": "开放申购", "赎回状态": "开放赎回", "手续费": 0.3},
                {"基金代码": "LOF001", "基金简称": "Growth LOF", "基金类型": "LOF", "申购状态": "暂停申购", "赎回状态": "开放赎回", "手续费": 0.8},
            ]
        )

    def open_fund_nav(self, fund_code: str) -> pd.DataFrame:
        if fund_code != "BOND01":
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {"净值日期": "2026-05-29", "单位净值": 1.01, "日增长率": 0.10},
                {"净值日期": "2026-06-02", "单位净值": 1.02, "日增长率": 0.15},
                {"净值日期": "2026-06-03", "单位净值": 1.03, "日增长率": 0.12},
            ]
        )

    def etf_fund_nav(self, fund_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if fund_code != "ETF001":
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {"净值日期": "2026-05-29", "单位净值": 2.01, "累计净值": 2.01, "日增长率": 0.40, "申购状态": "开放申购", "赎回状态": "开放赎回"},
                {"净值日期": "2026-06-02", "单位净值": 2.02, "累计净值": 2.02, "日增长率": 0.20, "申购状态": "开放申购", "赎回状态": "开放赎回"},
                {"净值日期": "2026-06-03", "单位净值": 2.05, "累计净值": 2.05, "日增长率": 1.49, "申购状态": "开放申购", "赎回状态": "开放赎回"},
            ]
        )

    def lof_fund_hist(self, fund_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if fund_code != "LOF001":
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {"日期": "2026-05-29", "收盘": 1.50, "涨跌幅": 0.60},
                {"日期": "2026-06-02", "收盘": 1.53, "涨跌幅": 2.00},
                {"日期": "2026-06-03", "收盘": 1.55, "涨跌幅": 1.31},
            ]
        )

    def benchmark_hist(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"日期": "2026-05-29", "收盘": 3900.0, "涨跌幅": 0.20},
                {"日期": "2026-06-02", "收盘": 3920.0, "涨跌幅": 0.51},
                {"日期": "2026-06-03", "收盘": 3910.0, "涨跌幅": -0.26},
            ]
        )
