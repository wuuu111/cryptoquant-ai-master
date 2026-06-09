# Fund Rotation Agent Spec

## Current Direction

The project is now fund-only.

The old stock quant workflow is no longer the supported main path. Legacy stock modules may remain in the repository temporarily, but the supported CLI, HTTP API, config, and documentation should all assume a fund / ETF allocation workflow.

## Product Goal

Build a personal-use fund rotation agent that:

- fetches fund and benchmark data from AkShare
- stores normalized local CSV files and PostgreSQL snapshots
- computes deterministic daily fund scores
- produces allocation and rebalance suggestions
- persists the latest daily cycle for audit and review
- supports scheduled daily execution
- supports manual portfolio input for personal use

## Supported Workflow

1. `sync-fund-data`
2. `fund-features`
3. `fund-cycle`
4. `latest-cycle`
5. `run-scheduler`

Optional offline workflow:

1. `sample-fund-data`
2. `fund-features`
3. `fund-cycle`

## Data Source

Primary source is AkShare.

The sync layer should write:

- `data/fund_pool.csv`
- `data/fund_nav_daily.csv`
- `data/fund_metadata.csv`
- `data/benchmark_index.csv`

When database mode is enabled, the same normalized data should also be written to PostgreSQL.

## Required Output

The system must output:

- ranked fund scores
- target weights
- delta weights
- suggested rebalance amounts
- blocked suggestions for audit
- deterministic review summary
- persisted cycle payload for latest-run retrieval

## Current Main Interfaces

- CLI: `sample-fund-data`, `sync-fund-data`, `fund-features`, `fund-cycle`, `latest-cycle`, `run-scheduler`, `serve`
- HTTP: `/fund-features`, `/latest-cycle`, `/sync-fund-data`, `/sample-fund-data`, `/fund-cycle`, `/scheduler/run-once`
- FastAPI: same fund-only endpoints

## Non-Goals

The current round does not include:

- stock signal generation
- stock execution export
- stock backtesting as a main workflow
- real broker fund order placement
- minute-level fund monitoring

## Personal-Use Requirements

The project should be usable by one person with:

- a local config file
- optional local portfolio JSON
- one-command AkShare sync
- one-command rebalance recommendation
- optional PostgreSQL persistence
- optional scheduled daily sync + cycle

## Implementation Notes

- deterministic risk rules remain authoritative
- AkShare sync should be testable with mock sources
- local CSV remains a valid offline boundary, but database-backed loading is the preferred online path
- existing stock modules are no longer part of the supported surface area
