from __future__ import annotations

import argparse
import json
from pathlib import Path

from .fund_fixtures import write_sample_fund_data
from .fund_live_cycle import cycle_from_settings, feature_snapshot_from_settings, latest_cycle_from_store
from .fund_scheduler import FundTaskScheduler
from .fund_sync import FundDataSyncer
from .fund_verifier import verify_postgres
from .schemas import PortfolioState, parse_portfolio
from .settings import RuntimeSettings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ashare-agent",
        description="Fund rotation agent CLI driven by AkShare and local CSV data.",
    )
    parser.add_argument("--config", default="config.real-local.yaml", help="Path to YAML config.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample_fund = subparsers.add_parser("sample-fund-data", help="Write deterministic offline sample fund CSV data.")
    sample_fund.add_argument("--days", type=int, default=180, help="Number of business days to generate.")
    sample_fund.add_argument("--end-date", default="", help="Optional end date in YYYY-MM-DD.")

    sync_fund = subparsers.add_parser("sync-fund-data", help="Fetch fund pool, NAV and benchmark CSVs from AkShare.")
    sync_fund.add_argument("--start-date", default="", help="Override config start_date in YYYYMMDD.")
    sync_fund.add_argument("--end-date", default="", help="Override config end_date in YYYYMMDD.")

    fund_features = subparsers.add_parser("fund-features", help="Preview latest fund feature snapshot from local CSV files.")
    fund_features.add_argument("--limit", type=int, default=20, help="Maximum number of funds to print.")

    fund_cycle = subparsers.add_parser("fund-cycle", help="Run fund rotation cycle from local CSV files.")
    fund_cycle.add_argument("--portfolio-file", default="", help="Optional JSON file with portfolio payload.")
    fund_cycle.add_argument("--account-id", default="default", help="Account id to use when portfolio-file is omitted.")

    latest_cycle = subparsers.add_parser("latest-cycle", help="Read the latest persisted cycle result from PostgreSQL.")

    verify_postgres_cmd = subparsers.add_parser(
        "verify-postgres",
        help="Run sync, cycle, and database row-count checks against the configured PostgreSQL database.",
    )
    verify_postgres_cmd.add_argument("--portfolio-file", default="", help="Optional JSON file with portfolio payload.")
    verify_postgres_cmd.add_argument("--account-id", default="default", help="Account id to use when portfolio-file is omitted.")
    verify_postgres_cmd.add_argument("--skip-sync", action="store_true", help="Skip AkShare sync and only verify cycle + row counts.")

    run_scheduler = subparsers.add_parser("run-scheduler", help="Run the scheduled sync + cycle job once or as a loop.")
    run_scheduler.add_argument("--account-id", default="default", help="Account id to use when scheduler portfolio_file is empty.")
    run_scheduler.add_argument("--run-once", action="store_true", help="Execute one scheduled run and exit.")

    serve = subparsers.add_parser("serve", help="Run fund-only local HTTP server.")
    serve.add_argument("--port", type=int, default=8710)
    serve.add_argument("--host", default="127.0.0.1")

    args = parser.parse_args(argv)
    settings = RuntimeSettings.load(args.config)
    settings.ensure_dirs()

    if args.command == "sample-fund-data":
        sample_report = write_sample_fund_data(
            settings.data_dir,
            periods=max(60, int(args.days)),
            end_date=args.end_date or None,
        )
        print_json(sample_report)
        return

    if args.command == "sync-fund-data":
        start_date = args.start_date or settings.start_date
        end_date = args.end_date or settings.end_date
        sync_report = FundDataSyncer(
            settings.data_dir,
            settings.fund_data,
            database=settings.database,
        ).sync(start_date=start_date, end_date=end_date)
        print_json(sync_report.__dict__)
        return

    if args.command == "fund-features":
        print_json(feature_snapshot_from_settings(settings, limit=max(0, int(args.limit))))
        return

    if args.command == "fund-cycle":
        portfolio = _load_portfolio_file(args.portfolio_file)
        print_json(cycle_from_settings(settings, portfolio=portfolio, account_id=args.account_id))
        return

    if args.command == "latest-cycle":
        print_json(latest_cycle_from_store(settings) or {})
        return

    if args.command == "verify-postgres":
        portfolio = _load_portfolio_file(args.portfolio_file)
        print_json(
            verify_postgres(
                settings,
                portfolio=portfolio,
                account_id=args.account_id,
                skip_sync=bool(args.skip_sync),
            )
        )
        return

    if args.command == "run-scheduler":
        scheduler = FundTaskScheduler(settings, account_id=args.account_id)
        if args.run_once:
            print_json(scheduler.run_once().__dict__)
            return
        scheduler.start()
        try:
            scheduler.wait()
        except KeyboardInterrupt:
            scheduler.stop()
        return

    if args.command == "serve":
        from .http_server import run_server

        run_server(args.host, args.port)
        return


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _load_portfolio_file(path: str) -> PortfolioState | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Portfolio file must contain a JSON object: {path}")
    return parse_portfolio(payload)


if __name__ == "__main__":
    main()
