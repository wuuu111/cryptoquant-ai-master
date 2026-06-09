import React from "react";
import { formatPercent } from "../lib/fundDashboard";
import { EmptyState } from "./EmptyState";

export function FundRankingPanel({ features }) {
  if (!features.items.length) {
    return (
      <EmptyState
        title="基金候选池还没准备好"
        detail="先完成一次基金数据同步，这里会展示按近 20 日表现排序的候选池。"
      />
    );
  }

  return (
    <div className="ranking-table">
      {features.items.slice(0, 8).map((item) => (
        <article key={item.fundCode} className="ranking-row">
          <div>
            <p>{item.fundCode}</p>
            <h3>{item.fundName}</h3>
            <span>{item.category || item.fundType || "fund"}</span>
          </div>
          <div className="ranking-metrics">
            <strong>{formatPercent(item.return20d)}</strong>
            <span>20d</span>
          </div>
        </article>
      ))}
    </div>
  );
}
