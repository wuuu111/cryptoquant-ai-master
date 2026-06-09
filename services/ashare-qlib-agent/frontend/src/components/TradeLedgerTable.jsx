import React from "react";
import { formatCurrency, formatDateTime } from "../lib/fundDashboard";
import { EmptyState } from "./EmptyState";

export function TradeLedgerTable({ trades }) {
  if (!trades.items.length) {
    return <EmptyState title="还没有交易流水" detail="一键调仓或手工买卖后，这里会出现最新流水。" />;
  }

  return (
    <div className="table-wrap">
      <table className="portfolio-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>基金</th>
            <th>方向</th>
            <th>金额</th>
            <th>来源</th>
            <th>备注</th>
          </tr>
        </thead>
        <tbody>
          {trades.items.map((item) => (
            <tr key={item.tradeId}>
              <td>{formatDateTime(item.tradeTime)}</td>
              <td>
                <div className="cell-stack">
                  <strong>{item.fundName}</strong>
                  <span>{item.symbol}</span>
                </div>
              </td>
              <td>{item.side}</td>
              <td>{formatCurrency(item.amount)}</td>
              <td>{item.source}</td>
              <td>{item.note || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
