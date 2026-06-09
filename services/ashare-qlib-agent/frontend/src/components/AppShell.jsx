import React from "react";
import { Activity, Bot, Database, RefreshCw, ShieldCheck, Wallet } from "lucide-react";

export function AppShell({
  activePage,
  onSelectPage,
  onRefresh,
  refreshing,
  activeApiBase,
  lastUpdated,
  health,
  actionMessage,
  children,
}) {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Bot size={24} />
          </div>
          <div>
            <h1>Fund Rotation Agent</h1>
            <p>多智能体基金决策工作台</p>
          </div>
        </div>

        <nav className="page-nav" aria-label="主导航">
          <button
            className={`nav-tab ${activePage === "today" ? "active" : ""}`}
            type="button"
            onClick={() => onSelectPage("today")}
          >
            <Activity size={15} />
            今日建议
          </button>
          <button
            className={`nav-tab ${activePage === "portfolio" ? "active" : ""}`}
            type="button"
            onClick={() => onSelectPage("portfolio")}
          >
            <Wallet size={15} />
            我的基金
          </button>
        </nav>

        <StatusPill
          icon={<Activity size={16} />}
          label="服务"
          value={health.ok ? "运行中" : "未连接"}
          tone={health.ok ? "good" : "bad"}
        />
        <StatusPill
          icon={<Database size={16} />}
          label="数据库"
          value={health.databaseEnabled ? "已接入" : "本地 CSV"}
          tone={health.databaseEnabled ? "good" : "neutral"}
        />
        <StatusPill
          icon={<ShieldCheck size={16} />}
          label="定时任务"
          value={health.schedulerEnabled ? "已启用" : "手动刷新"}
          tone={health.schedulerEnabled ? "good" : "warn"}
        />

        <button className="refresh-button" type="button" onClick={onRefresh} disabled={refreshing}>
          <RefreshCw size={16} className={refreshing ? "spin" : ""} />
          {refreshing ? "刷新中" : "跑一轮今日周期"}
        </button>

        <div className="sidebar-note">
          <span>API</span>
          <code>{activeApiBase}</code>
        </div>
        <div className="sidebar-note">
          <span>更新</span>
          <strong>{lastUpdated || "-"}</strong>
        </div>
        {actionMessage ? (
          <div className="sidebar-callout">
            <strong>最近动作</strong>
            <p>{actionMessage}</p>
          </div>
        ) : null}
      </aside>

      {children}
    </main>
  );
}

function StatusPill({ icon, label, value, tone }) {
  return (
    <div className={`status-pill ${tone}`}>
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
