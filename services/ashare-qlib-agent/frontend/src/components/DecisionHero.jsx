import React from "react";
import { AlertTriangle, CheckCircle2, ShieldCheck, TrendingUp } from "lucide-react";
import { formatNumber, gateTone } from "../lib/fundDashboard";

export function DecisionHero({ cycle, summary }) {
  return (
    <section className="hero-grid">
      <div className={`hero-card ${summary.tone}`}>
        <p className="eyebrow">Today Recommendation</p>
        <h2>{summary.headline}</h2>
        <p className="hero-detail">{summary.detail}</p>
        <div className="hero-tags">
          <span className={`hero-tag ${gateTone(cycle.market.gate)}`}>
            <ShieldCheck size={14} />
            {cycle.market.regime || "NO_CYCLE"} / {cycle.market.gate || "WAIT"}
          </span>
          <span className="hero-tag muted">
            <TrendingUp size={14} />
            市场分数 {formatNumber(cycle.market.score, 3)}
          </span>
        </div>
      </div>

      <div className="hero-sidecards">
        <MetricCard
          title="可执行建议"
          value={String(summary.actionableCount)}
          detail={`阻断 ${summary.blockedCount} 条`}
          tone={summary.actionableCount > 0 ? "good" : "warn"}
          icon={<CheckCircle2 size={18} />}
        />
        <MetricCard
          title="建议总额"
          value={summary.totalDeltaValueLabel}
          detail="按绝对变动金额汇总"
          tone="neutral"
          icon={<TrendingUp size={18} />}
        />
        <MetricCard
          title="风险门控"
          value={cycle.market.gate || "-"}
          detail={cycle.market.reason || "等待新的基金周期"}
          tone={gateTone(cycle.market.gate)}
          icon={summary.blockedCount > 0 ? <AlertTriangle size={18} /> : <ShieldCheck size={18} />}
        />
      </div>
    </section>
  );
}

function MetricCard({ title, value, detail, tone, icon }) {
  return (
    <article className={`metric-card ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{title}</span>
        <strong>{value}</strong>
        <p>{detail}</p>
      </div>
    </article>
  );
}
