import React from "react";
import { ChevronDown, Lock, Wallet } from "lucide-react";
import { EmptyState } from "./EmptyState";

export function SuggestionBoard({ suggestions, onApply = () => {}, onManualAdjust = () => {}, onInspect = () => {} }) {
  if (!suggestions.length) {
    return (
      <EmptyState
        title="今日没有新的基金动作"
        detail="等下一轮周期完成后，这里会显示申购、减仓或观察建议。"
      />
    );
  }

  return (
    <div className="suggestion-board">
      {suggestions.map((item) => (
        <details key={`${item.symbol}-${item.action}`} className={`suggestion-card ${item.tone}`}>
          <summary>
            <div className="suggestion-head">
              <div>
                <p className="suggestion-symbol">{item.symbol}</p>
                <h3>{item.fundName}</h3>
                <span className="suggestion-action">{item.actionLabel}</span>
              </div>
              <div className="suggestion-amount">
                <strong>{item.amountLabel}</strong>
                <span>{item.blocked ? "已阻断" : "建议金额"}</span>
              </div>
            </div>
            <div className="suggestion-meta">
              <span className={`pill ${item.blocked ? "risk" : "good"}`}>
                {item.blocked ? <Lock size={12} /> : <Wallet size={12} />}
                {item.blocked ? "风险阻断" : item.applied ? "已记账" : "可执行"}
              </span>
              <span className="pill neutral">当前 {item.currentWeightLabel}</span>
              <span className="pill neutral">目标 {item.targetWeightLabel}</span>
              <span className={`pill ${item.deltaWeight >= 0 ? "good" : "warn"}`}>偏移 {item.deltaWeightLabel}</span>
              <ChevronDown size={14} className="summary-caret" />
            </div>
          </summary>
          <div className="suggestion-detail">
            <p>{item.reason || "本条建议未附带额外解释。"} </p>
            <div className="suggestion-actions">
              {!item.blocked && !item.applied ? (
                <button type="button" className="mock-button" onClick={() => onApply(item)}>
                  一键调仓
                </button>
              ) : item.applied ? (
                <button type="button" className="mock-button" disabled>
                  已记账
                </button>
              ) : (
                <button type="button" className="jump-button" onClick={() => onInspect(item)}>
                  查看协作理由
                </button>
              )}
              <button type="button" className="jump-button" onClick={() => onManualAdjust(item)}>
                手动调整
              </button>
            </div>
          </div>
        </details>
      ))}
    </div>
  );
}
