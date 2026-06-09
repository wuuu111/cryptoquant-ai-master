import React from "react";
import { Bot, CircleAlert, SearchCheck, ShieldCheck, Wallet } from "lucide-react";
import { EmptyState } from "./EmptyState";

const ICONS = {
  MarketDetectAgent: SearchCheck,
  FundFactorAgent: Bot,
  PortfolioAgent: Wallet,
  RiskAgent: ShieldCheck,
  ReviewAgent: CircleAlert,
};

export function AgentDecisionChain({ steps }) {
  if (!steps.length) {
    return (
      <EmptyState
        title="多智能体链路尚未出现"
        detail="一旦日频周期跑完，这里会显示市场、评分、组合、风控和复核的关键裁决。"
      />
    );
  }

  return (
    <div className="agent-chain">
      {steps.map((step, index) => {
        const Icon = ICONS[step.name] || Bot;
        return (
          <article key={`${step.name}-${index}`} className={`agent-step ${step.status}`}>
            <div className="agent-step-top">
              <span className="agent-step-icon"><Icon size={16} /></span>
              <div className="agent-step-copy">
                <p className="agent-step-label">{step.label}</p>
                <h3 className="agent-step-name">{step.name}</h3>
              </div>
            </div>
            <p className="agent-step-summary">{step.summary}</p>
          </article>
        );
      })}
    </div>
  );
}
