# Fund Rotation Agent Tasks

## Phase Goal

Complete the fund-only workflow for personal use.

## Task Group A: Fund Data Sync

- add AkShare-based fund sync
- support open funds, ETFs, and LOFs
- write normalized CSV files
- fetch benchmark index history
- support config-based fund selection

## Task Group B: Fund Decision Pipeline

- keep local CSV loader as the runtime input boundary
- compute fund features from synced CSVs
- score funds deterministically
- build target allocation by portfolio mode
- apply deterministic risk constraints
- emit rebalance suggestions

## Task Group C: Fund-Only Interfaces

- make CLI fund-only
- make HTTP server fund-only
- make FastAPI app fund-only
- keep optional local portfolio JSON input

## Task Group D: Personal-Use Experience

- provide sample fund data generation
- provide example portfolio JSON
- provide feature preview command
- document the recommended three-step workflow
- provide a local PostgreSQL config template
- provide a one-command PostgreSQL verification path

## Task Group E: Quality

- add sync-layer tests with mocked AkShare source
- keep fund cycle and portfolio tests passing
- keep mypy passing
- keep env-based config loading covered by tests

## Current Priority Order

1. AkShare sync stability
2. fund-cycle usability with real portfolio input
3. better rebalance explanation
4. richer metadata such as manager and AUM

## Deferred

- delete every legacy stock module immediately
- build a new frontend dashboard
- add broker execution for funds
- support intraday trading decisions
