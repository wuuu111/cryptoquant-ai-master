import React from "react";
import { formatCurrency, formatPercent, formatSignedPercent } from "../lib/fundDashboard";
import { EmptyState } from "./EmptyState";

export function PortfolioCompareTable({ rows }) {
  if (!rows.length) {
    return (
      <EmptyState
        title="还没有基金持仓可对比"
        detail="当前没有持仓，或今日周期尚未生成目标组合。"
      />
    );
  }

  return (
    <div className="table-wrap">
      <table className="portfolio-table">
        <thead>
          <tr>
            <th>基金</th>
            <th>当前市值</th>
            <th>当前权重</th>
            <th>目标权重</th>
            <th>偏离</th>
            <th>建议</th>
            <th>金额</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.symbol}>
              <td>
                <div className="cell-stack">
                  <strong>{row.fundName}</strong>
                  <span>{row.symbol}</span>
                </div>
              </td>
              <td>{formatCurrency(row.marketValue)}</td>
              <td>{formatPercent(row.currentWeight)}</td>
              <td>{formatPercent(row.targetWeight)}</td>
              <td>{formatSignedPercent(row.drift)}</td>
              <td>
                <span className={`pill ${row.blocked ? "risk" : "neutral"}`}>{row.action}</span>
              </td>
              <td>{row.amountLabel}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
