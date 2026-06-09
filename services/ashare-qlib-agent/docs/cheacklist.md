# Fund Rotation Agent Checklist

## Direction

- [x] Project main path is fund-only
- [x] Stock workflow is no longer the supported default
- [x] Personal-use workflow is defined

## Sync Layer

- [x] AkShare fund sync module exists
- [x] fund pool CSV is generated
- [x] fund NAV CSV is generated
- [x] fund metadata CSV is generated
- [x] benchmark CSV is generated
- [x] sync layer is covered by tests

## Runtime

- [x] local CSV loader still works
- [x] fund feature snapshot exists
- [x] fund scoring exists
- [x] fund portfolio construction exists
- [x] fund risk filtering exists
- [x] rebalance suggestion output exists

## Interfaces

- [x] CLI is fund-only
- [x] HTTP server is fund-only
- [x] FastAPI app is fund-only
- [x] example portfolio JSON exists
- [x] example request exists
- [x] PostgreSQL verify command exists
- [x] dedicated PostgreSQL config template exists

## Verification

- [x] mypy passes
- [x] pytest passes
- [x] sample fund workflow test exists
- [x] sync workflow test exists
- [x] env placeholder loading is covered by tests
- [x] DB-backed verify workflow is covered by tests

## Next Useful Work

- [ ] support richer fund metadata from AkShare
- [ ] improve theme / style concentration constraints
- [ ] add import adapters for personal holdings CSV
- [ ] improve explanation quality for rebalance decisions
