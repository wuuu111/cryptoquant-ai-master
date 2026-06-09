from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal, cast


GateState = Literal["ALLOW_FULL", "ALLOW_REDUCED", "BLOCK_NEW_RISK"]
MarketRegime = Literal["BULL_TREND", "BEAR_TREND", "RANGE", "RISK_OFF", "UNKNOWN"]
SignalAction = Literal["BUY", "SELL", "HOLD"]
OrderSide = Literal["BUY", "SELL"]
RebalanceAction = Literal["INCREASE", "DECREASE", "HOLD"]


@dataclass(frozen=True)
class InstrumentFeature:
    symbol: str
    close: float
    pct_chg: float = 0.0
    turnover: float = 0.0
    market_cap: float = 0.0
    industry: str = "UNKNOWN"
    category: str = "UNKNOWN"
    fund_type: str = "UNKNOWN"
    tracking_index: str = ""
    risk_level: str = "UNKNOWN"
    enabled: bool = True
    purchase_status: str = "open"
    redemption_status: str = "open"
    data_as_of: str = ""
    stale: bool = False
    is_st: bool = False
    suspended: bool = False
    limit_up: bool = False
    limit_down: bool = False
    factors: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketSnapshot:
    as_of: str
    benchmark_returns: dict[str, float]
    breadth: dict[str, float]
    instruments: list[InstrumentFeature]


@dataclass(frozen=True)
class Position:
    symbol: str
    shares: int
    available_shares: int
    market_value: float
    cost_basis: float = 0.0
    industry: str = "UNKNOWN"
    category: str = "UNKNOWN"
    fund_type: str = "UNKNOWN"
    weight: float = 0.0


@dataclass(frozen=True)
class PortfolioState:
    cash: float
    equity: float
    positions: list[Position] = field(default_factory=list)


@dataclass(frozen=True)
class MarketRegimeResult:
    regime: MarketRegime
    gate: GateState
    score: float
    reason: str
    exposure_multiplier: float


@dataclass(frozen=True)
class FactorScore:
    symbol: str
    industry: str
    close: float
    factor_score: float
    model_score: float | None
    combined_score: float
    rank: int
    diagnostics: dict[str, float] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: SignalAction
    confidence: float
    target_weight: float
    score: float
    reason: str


@dataclass(frozen=True)
class TargetPosition:
    symbol: str
    target_weight: float
    target_value: float
    reason: str


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: OrderSide
    shares: int
    estimated_value: float
    reason: str
    blocked: bool = False


@dataclass(frozen=True)
class RebalanceSuggestion:
    symbol: str
    action: RebalanceAction
    current_weight: float
    target_weight: float
    delta_weight: float
    current_value: float
    target_value: float
    delta_value: float
    reason: str
    blocked: bool = False


@dataclass(frozen=True)
class ReviewReport:
    summary: str
    risk_notes: list[str]
    metrics: dict[str, float]


@dataclass(frozen=True)
class EvolutionExperiment:
    name: str
    hypothesis: str
    validation_plan: str
    approval_required: bool = True


@dataclass(frozen=True)
class AgentStep:
    name: str
    role: str
    framework: str
    model: str
    tools: list[str] = field(default_factory=list)
    status: str = "ok"
    summary: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    next_action: str = ""


@dataclass(frozen=True)
class CollaborationEvent:
    agent: str
    kind: str
    summary: str
    severity: str = "info"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CycleResult:
    cycle_id: str
    market: MarketRegimeResult
    scores: list[FactorScore]
    signals: list[Signal]
    targets: list[TargetPosition]
    orders: list[OrderIntent]
    review: ReviewReport
    evolution: list[EvolutionExperiment]
    suggestions: list[RebalanceSuggestion] = field(default_factory=list)
    workflow: str = "legacy"
    agent_trace: list[AgentStep] = field(default_factory=list)
    collaboration_events: list[CollaborationEvent] = field(default_factory=list)
    agent_messages: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    blackboard: dict[str, Any] = field(default_factory=dict)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(cast(Any, value)).items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def parse_instrument(payload: dict[str, Any]) -> InstrumentFeature:
    return InstrumentFeature(
        symbol=str(payload["symbol"]),
        close=float(payload.get("close", 0)),
        pct_chg=float(payload.get("pct_chg", 0)),
        turnover=float(payload.get("turnover", 0)),
        market_cap=float(payload.get("market_cap", 0)),
        industry=str(payload.get("industry", "UNKNOWN")),
        category=str(payload.get("category", payload.get("industry", "UNKNOWN"))),
        fund_type=str(payload.get("fund_type", "UNKNOWN")),
        tracking_index=str(payload.get("tracking_index", "")),
        risk_level=str(payload.get("risk_level", "UNKNOWN")),
        enabled=bool(payload.get("enabled", True)),
        purchase_status=str(payload.get("purchase_status", "open")),
        redemption_status=str(payload.get("redemption_status", "open")),
        data_as_of=str(payload.get("data_as_of", "")),
        stale=bool(payload.get("stale", False)),
        is_st=bool(payload.get("is_st", False)),
        suspended=bool(payload.get("suspended", False)),
        limit_up=bool(payload.get("limit_up", False)),
        limit_down=bool(payload.get("limit_down", False)),
        factors={str(k): float(v) for k, v in dict(payload.get("factors", {})).items()},
    )


def parse_snapshot(payload: dict[str, Any]) -> MarketSnapshot:
    return MarketSnapshot(
        as_of=str(payload.get("as_of", "")),
        benchmark_returns={str(k): float(v) for k, v in dict(payload.get("benchmark_returns", {})).items()},
        breadth={str(k): float(v) for k, v in dict(payload.get("breadth", {})).items()},
        instruments=[parse_instrument(item) for item in payload.get("instruments", [])],
    )


def parse_position(payload: dict[str, Any]) -> Position:
    return Position(
        symbol=str(payload["symbol"]),
        shares=int(payload.get("shares", 0)),
        available_shares=int(payload.get("available_shares", payload.get("shares", 0))),
        market_value=float(payload.get("market_value", 0)),
        cost_basis=float(payload.get("cost_basis", 0)),
        industry=str(payload.get("industry", "UNKNOWN")),
        category=str(payload.get("category", payload.get("industry", "UNKNOWN"))),
        fund_type=str(payload.get("fund_type", "UNKNOWN")),
        weight=float(payload.get("weight", 0)),
    )


def parse_portfolio(payload: dict[str, Any]) -> PortfolioState:
    return PortfolioState(
        cash=float(payload.get("cash", 0)),
        equity=float(payload.get("equity", 0)),
        positions=[parse_position(item) for item in payload.get("positions", [])],
    )
