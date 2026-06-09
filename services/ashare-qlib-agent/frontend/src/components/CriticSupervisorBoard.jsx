import React from "react";
import { AlertTriangle, ArrowRightLeft, Bot, CheckCircle2, ShieldAlert, Stamp } from "lucide-react";
import { EmptyState } from "./EmptyState";
import { formatPercent } from "../lib/fundDashboard";

export function CriticSupervisorBoard({ review }) {
  if (!review) {
    return (
      <EmptyState
        title="裁决分歧板暂不可用"
        detail="等下一轮基金周期完成后，这里会展示提案、异议、裁决和最终结果。"
      />
    );
  }

  return (
    <div className="decision-review-board">
      <section className="decision-lane-grid">
        <LaneCard
          icon={<Bot size={16} />}
          title="组合提案"
          tone="neutral"
          lines={[
            `${review.proposal.targetCount} 个目标持仓`,
            `计划总暴露 ${review.proposal.targetExposureLabel}`,
            review.proposal.topFunds.length ? `核心目标: ${review.proposal.topFunds.join("、")}` : "暂无目标基金",
          ]}
          chips={review.proposal.categoryWeights.slice(0, 4).map((item) => `${item.name} ${item.label}`)}
        />

        <LaneCard
          icon={<ShieldAlert size={16} />}
          title="Critic 异议"
          tone={review.critic.blockerCount ? "bad" : review.critic.warningCount ? "warn" : "good"}
          lines={[
            `blocker ${review.critic.blockerCount} 条`,
            `warning ${review.critic.warningCount} 条`,
            review.critic.objections[0]?.summary || "没有新的执行前异议。",
          ]}
          chips={review.critic.objections.slice(0, 4).map((item) => item.summary)}
        />

        <LaneCard
          icon={<Stamp size={16} />}
          title="Supervisor 裁决"
          tone={review.supervisor.requiresHumanReview ? "warn" : "good"}
          lines={[
            `${review.supervisor.routeLabel} / ${review.supervisor.decisionLabel}`,
            `置信度 ${formatPercent(review.supervisor.confidence)}`,
            review.supervisor.reasoningSummary,
          ]}
          chips={[
            review.supervisor.requiresHumanReview ? "需人工复核" : "可自动推进",
            ...review.supervisor.requiredModifications.slice(0, 3),
          ]}
        />

        <LaneCard
          icon={<CheckCircle2 size={16} />}
          title="最终结果"
          tone={review.final.blockedCount ? "warn" : "good"}
          lines={[
            `可执行 ${review.final.actionableCount} 条`,
            `阻断 ${review.final.blockedCount} 条`,
            review.final.summary || "等待最终复核摘要。",
          ]}
          chips={[review.supervisor.routeLabel, ...review.final.riskNotes.slice(0, 4)]}
        />
      </section>

      <section className="dispute-table">
        <header className="dispute-table-head">
          <strong>主要分歧点</strong>
          <span>把提案、Critic 异议和 Supervisor 结果放在同一行看。</span>
        </header>

        <div className="dispute-rows">
          {review.disputes.map((item) => (
            <article key={item.id} className={`dispute-row ${item.severity}`}>
              <div className="dispute-topic">
                <ArrowRightLeft size={14} />
                <strong>{item.title}</strong>
              </div>
              <div className="dispute-column">
                <span>提案</span>
                <p>{item.proposal}</p>
              </div>
              <div className="dispute-column critic">
                <span>Critic</span>
                <p>{item.critic}</p>
              </div>
              <div className="dispute-column supervisor">
                <span>Supervisor</span>
                <p>{item.outcome}</p>
              </div>
            </article>
          ))}
        </div>

        {review.supervisor.supportingEvidence.length || review.supervisor.opposingEvidence.length ? (
          <div className="evidence-shelves">
            <EvidenceShelf
              title="支持证据"
              tone="good"
              icon={<CheckCircle2 size={14} />}
              items={review.supervisor.supportingEvidence}
            />
            <EvidenceShelf
              title="反对证据"
              tone="bad"
              icon={<AlertTriangle size={14} />}
              items={review.supervisor.opposingEvidence}
            />
          </div>
        ) : null}
      </section>
    </div>
  );
}

function LaneCard({ icon, title, tone, lines, chips }) {
  return (
    <article className={`decision-lane ${tone}`}>
      <div className="decision-lane-head">
        {icon}
        <strong>{title}</strong>
      </div>
      <div className="decision-lane-copy">
        {lines.filter(Boolean).map((line, index) => (
          <p key={`${title}-${index}`}>{line}</p>
        ))}
      </div>
      {chips.filter(Boolean).length ? (
        <div className="decision-chip-row">
          {chips.filter(Boolean).map((chip, index) => (
            <span key={`${title}-chip-${index}`} className="decision-chip">{chip}</span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function EvidenceShelf({ title, tone, icon, items }) {
  return (
    <article className={`evidence-shelf ${tone}`}>
      <div className="evidence-shelf-head">
        {icon}
        <strong>{title}</strong>
      </div>
      <div className="decision-chip-row">
        {items.map((item, index) => (
          <span key={`${title}-${index}`} className="decision-chip">{item}</span>
        ))}
      </div>
    </article>
  );
}
