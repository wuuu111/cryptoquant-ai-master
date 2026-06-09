import React, { startTransition, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlertTriangle, BarChart3, BrainCircuit, ClipboardList, RefreshCw, ShieldCheck, Wallet } from "lucide-react";
import "./styles.css";
import {
  applySuggestion,
  createTrade,
  fetchAccount,
  fetchFundFeatures,
  fetchHealth,
  fetchLatestCycle,
  fetchPositions,
  fetchTrades,
  getDefaultApiBase,
  runSchedulerOnce,
  saveAccount,
} from "./lib/api";
import {
  buildFundLookup,
  buildDecisionReview,
  buildPortfolioRows,
  formatCurrency,
  formatDateTime,
  gateTone,
  normalizeAccountPayload,
  normalizeCyclePayload,
  normalizeFundFeaturesPayload,
  normalizeHealthPayload,
  normalizePositionsPayload,
  normalizeTradesPayload,
  summarizeDecision,
} from "./lib/fundDashboard";
import { AccountOverview } from "./components/AccountOverview";
import { AppShell } from "./components/AppShell";
import { AgentDecisionChain } from "./components/AgentDecisionChain";
import { AgentTimeline } from "./components/AgentTimeline";
import { DecisionHero } from "./components/DecisionHero";
import { EmptyState } from "./components/EmptyState";
import { FundRankingPanel } from "./components/FundRankingPanel";
import { ManualTradeDrawer } from "./components/ManualTradeDrawer";
import { PortfolioCompareTable } from "./components/PortfolioCompareTable";
import { RiskReviewPanel } from "./components/RiskReviewPanel";
import { SuggestionBoard } from "./components/SuggestionBoard";
import { TradeLedgerTable } from "./components/TradeLedgerTable";
import { CriticSupervisorBoard } from "./components/CriticSupervisorBoard";

function App() {
  const [activePage, setActivePage] = useState("today");
  const [activeApiBase, setActiveApiBase] = useState(getDefaultApiBase());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const [health, setHealth] = useState(normalizeHealthPayload({}));
  const [fundFeatures, setFundFeatures] = useState(normalizeFundFeaturesPayload({}));
  const [account, setAccount] = useState(normalizeAccountPayload({}));
  const [positions, setPositions] = useState(normalizePositionsPayload({}));
  const [trades, setTrades] = useState(normalizeTradesPayload({}));
  const [cycle, setCycle] = useState(normalizeCyclePayload({}));
  const [manualTradeOpen, setManualTradeOpen] = useState(false);
  const [manualTradeSeed, setManualTradeSeed] = useState(null);

  async function loadSnapshot({ preserveMessage = false } = {}) {
    if (!preserveMessage) {
      setActionMessage("");
    }
    setError("");
    const [healthResult, featureResult, accountResult, positionsResult, tradesResult, cycleResult] = await Promise.allSettled([
      fetchHealth(activeApiBase, setActiveApiBase),
      fetchFundFeatures(activeApiBase, setActiveApiBase),
      fetchAccount(activeApiBase, setActiveApiBase),
      fetchPositions(activeApiBase, setActiveApiBase),
      fetchTrades(activeApiBase, setActiveApiBase),
      fetchLatestCycle(activeApiBase, setActiveApiBase),
    ]);

    const nextHealth = healthResult.status === "fulfilled"
      ? normalizeHealthPayload(healthResult.value)
      : normalizeHealthPayload({});
    const nextFeatures = featureResult.status === "fulfilled"
      ? normalizeFundFeaturesPayload(featureResult.value)
      : normalizeFundFeaturesPayload({});
    const nextAccount = accountResult.status === "fulfilled"
      ? normalizeAccountPayload(accountResult.value)
      : normalizeAccountPayload({});
    const nextPositions = positionsResult.status === "fulfilled"
      ? normalizePositionsPayload(positionsResult.value, nextAccount)
      : normalizePositionsPayload({}, nextAccount);
    const nextTrades = tradesResult.status === "fulfilled"
      ? normalizeTradesPayload(tradesResult.value)
      : normalizeTradesPayload({});
    const nextLookup = buildFundLookup(nextFeatures, nextPositions);
    const nextCycle = cycleResult.status === "fulfilled"
      ? normalizeCyclePayload(cycleResult.value, nextLookup)
      : normalizeCyclePayload({}, nextLookup);

    const failures = [
      healthResult.status === "rejected" ? "健康检查失败" : "",
      featureResult.status === "rejected" ? "基金特征不可用" : "",
      accountResult.status === "rejected" ? "账户总览不可用" : "",
      positionsResult.status === "rejected" ? "当前持仓不可用" : "",
      tradesResult.status === "rejected" ? "交易流水不可用" : "",
      cycleResult.status === "rejected" ? "最新周期不可用" : "",
    ].filter(Boolean);

    setHealth(nextHealth);
    setFundFeatures(nextFeatures);
    setAccount(nextAccount);
    setPositions(nextPositions);
    setTrades(nextTrades);
    setCycle(nextCycle);
    setLastUpdated(new Date().toLocaleString("zh-CN", { hour12: false }));
    if (failures.length) {
      setError(failures.join("；"));
    }
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadSnapshot()
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError.message || "加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onRefresh() {
    setRefreshing(true);
    setError("");
    setActionMessage("");
    try {
      const schedulerResult = await runSchedulerOnce(activeApiBase, setActiveApiBase);
      await loadSnapshot({ preserveMessage: true });
      setActionMessage(
        schedulerResult.latest_cycle_id
          ? `已完成一轮同步与决策刷新，最新周期 ${schedulerResult.latest_cycle_id}。`
          : "已完成一轮同步与决策刷新。",
      );
    } catch (requestError) {
      setError(requestError.message || "刷新失败");
    } finally {
      setRefreshing(false);
    }
  }

  const summary = useMemo(() => summarizeDecision(cycle), [cycle]);
  const portfolioRows = useMemo(() => buildPortfolioRows(cycle, positions, fundFeatures), [cycle, positions, fundFeatures]);
  const decisionReview = useMemo(() => buildDecisionReview(cycle), [cycle]);

  async function onApplySuggestion(item) {
    setError("");
    await applySuggestion(item.suggestionId, {}, activeApiBase, setActiveApiBase);
    await loadSnapshot({ preserveMessage: true });
    setActionMessage(`已将 ${item.fundName} 的建议写入本地账本。`);
  }

  function onOpenManualTrade(seed = null) {
    setManualTradeSeed(seed);
    setManualTradeOpen(true);
  }

  async function onSubmitManualTrade(payload) {
    setError("");
    await createTrade(payload, activeApiBase, setActiveApiBase);
    await loadSnapshot({ preserveMessage: true });
    setManualTradeOpen(false);
    setManualTradeSeed(null);
    setActionMessage(`已记录 ${payload.symbol || payload.fund_name} 的手工买卖。`);
  }

  async function onSaveAccount(payload) {
    setError("");
    await saveAccount({ account_id: account.accountId, base_currency: account.baseCurrency, ...payload }, activeApiBase, setActiveApiBase);
    await loadSnapshot({ preserveMessage: true });
    setActionMessage("已更新账户总资产与现金口径。");
  }

  return (
    <AppShell
      activePage={activePage}
      onSelectPage={(page) => startTransition(() => setActivePage(page))}
      onRefresh={onRefresh}
      refreshing={refreshing}
      activeApiBase={activeApiBase}
      lastUpdated={lastUpdated}
      health={health}
      actionMessage={actionMessage}
    >
      <section className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Daily Fund Workbench</p>
            <h2>{activePage === "today" ? "今日建议" : "我的基金持仓"}</h2>
          </div>
          <div className={`gate-card ${gateTone(cycle.market.gate)}`}>
            <ShieldCheck size={18} />
            <div>
              <span>{cycle.market.regime || "NO_CYCLE"}</span>
              <strong>{cycle.market.gate || "WAIT"}</strong>
            </div>
          </div>
        </header>

        {error ? (
          <Notice tone="bad" icon={<AlertTriangle size={18} />} message={error} />
        ) : null}

        {loading ? (
          <EmptyState
            title="正在加载基金工作台"
            detail="正在读取最新周期、基金候选池和当前持仓。"
            action={<div className="loading-inline"><RefreshCw size={14} className="spin" /> 请稍候</div>}
          />
        ) : activePage === "today" ? (
          <TodayView
            cycle={cycle}
            summary={summary}
            fundFeatures={fundFeatures}
            onApplySuggestion={onApplySuggestion}
            onManualTrade={onOpenManualTrade}
            onInspectSuggestion={(item) => setActionMessage(item.reason || `${item.fundName} 当前被风险规则阻断。`)}
            onOpenPortfolio={() => startTransition(() => setActivePage("portfolio"))}
          />
        ) : (
          <PortfolioView
            cycle={cycle}
            account={account}
            positions={positions}
            trades={trades}
            rows={portfolioRows}
            fundFeatures={fundFeatures}
            decisionReview={decisionReview}
            onSaveAccount={onSaveAccount}
            onManualTrade={onOpenManualTrade}
          />
        )}

        <ManualTradeDrawer
          open={manualTradeOpen}
          seed={manualTradeSeed}
          onClose={() => setManualTradeOpen(false)}
          onSubmit={onSubmitManualTrade}
        />
      </section>
    </AppShell>
  );
}

function TodayView({ cycle, summary, fundFeatures, onApplySuggestion, onManualTrade, onInspectSuggestion, onOpenPortfolio }) {
  return (
    <>
      <DecisionHero cycle={cycle} summary={summary} />

      <section className="panel-grid two-col">
        <Panel title="今日建议清单" icon={<Wallet size={18} />}>
          <SuggestionBoard
            suggestions={cycle.suggestions}
            onApply={onApplySuggestion}
            onManualAdjust={onManualTrade}
            onInspect={onInspectSuggestion}
          />
        </Panel>
        <Panel title="关键协作链" icon={<BrainCircuit size={18} />}>
          <AgentDecisionChain steps={cycle.agentChain} />
        </Panel>
      </section>

      <section className="panel-grid two-col">
        <Panel title="风险审查" icon={<ShieldCheck size={18} />}>
          <RiskReviewPanel review={cycle.review} />
        </Panel>
        <Panel title="候选基金预览" icon={<BarChart3 size={18} />}>
          <FundRankingPanel features={fundFeatures} />
        </Panel>
      </section>

      <Panel title="继续查看" icon={<ClipboardList size={18} />}>
        <div className="jump-panel">
          <p>如果你要看完整多智能体协作、当前持仓与目标组合对比，直接进入“我的基金”页。</p>
          <button className="jump-button" type="button" onClick={onOpenPortfolio}>
            查看完整协作与组合对比
          </button>
        </div>
      </Panel>
    </>
  );
}

function PortfolioView({ cycle, account, positions, trades, rows, fundFeatures, decisionReview, onSaveAccount, onManualTrade }) {
  const actionableCount = cycle.suggestions.filter((item) => !item.blocked).length;

  return (
    <>
      <Panel title="账户与收益" icon={<Wallet size={18} />}>
        <AccountOverview account={account} onSave={onSaveAccount} />
      </Panel>

      <Panel title="当前持仓 vs 目标组合" icon={<Wallet size={18} />}>
        <PortfolioCompareTable rows={rows} />
      </Panel>

      <section className="panel-grid two-col">
        <Panel title="候选基金排名" icon={<BarChart3 size={18} />}>
          <FundRankingPanel features={fundFeatures} />
        </Panel>
        <Panel title="最新复核摘要" icon={<ClipboardList size={18} />}>
          <RiskReviewPanel review={cycle.review} />
        </Panel>
      </section>

      <section className="panel-grid two-col">
        <Panel title="账户概览" icon={<ShieldCheck size={18} />}>
          <div className="metric-strip">
            <Metric title="持仓基金数" value={String(positions.items.length)} detail={`最近更新 ${formatDateTime(positions.updatedAt)}`} />
            <Metric title="当前现金" value={formatCurrency(account.cashBalance)} detail="本地账本现金余额" />
            <Metric title="可执行建议" value={String(actionableCount)} detail={`本轮共 ${cycle.suggestions.length} 条建议`} />
            <Metric title="候选池" value={String(fundFeatures.count)} detail={fundFeatures.asOf ? `as of ${fundFeatures.asOf}` : "等待基金数据"} />
          </div>
        </Panel>
        <Panel title="手工买卖入口" icon={<ClipboardList size={18} />}>
          <div className="jump-panel">
            <p>支持通过基金代码或名称手工记录 BUY / SELL，并立即更新收益和持仓。</p>
            <button className="jump-button" type="button" onClick={() => onManualTrade(null)}>
              打开手工记账
            </button>
          </div>
        </Panel>
      </section>

      <Panel title="交易流水" icon={<ClipboardList size={18} />}>
        <TradeLedgerTable trades={trades} />
      </Panel>

      <Panel title="Supervisor / Critic 裁决差异" icon={<BrainCircuit size={18} />}>
        <CriticSupervisorBoard review={decisionReview} />
      </Panel>

      <Panel title="完整多智能体协作" icon={<BrainCircuit size={18} />}>
        <AgentTimeline trace={cycle.trace} events={cycle.events} messages={cycle.agentMessages} />
      </Panel>
    </>
  );
}

function Panel({ title, icon, children }) {
  return (
    <section className="panel">
      <header className="panel-header">
        <div>
          {icon}
          <h3>{title}</h3>
        </div>
      </header>
      {children}
    </section>
  );
}

function Metric({ title, value, detail }) {
  return (
    <article className="strip-metric">
      <span>{title}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function Notice({ tone, icon, message }) {
  return (
    <div className={`notice ${tone}`}>
      {icon}
      <span>{message}</span>
    </div>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
