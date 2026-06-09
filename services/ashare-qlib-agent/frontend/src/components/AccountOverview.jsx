import React, { useEffect, useState } from "react";
import { formatCurrency, formatPercent } from "../lib/fundDashboard";

export function AccountOverview({ account, onSave }) {
  const [targetTotalAssets, setTargetTotalAssets] = useState(account.targetTotalAssets || 0);
  const [cashBalance, setCashBalance] = useState(account.cashBalance || 0);

  useEffect(() => {
    setTargetTotalAssets(account.targetTotalAssets || 0);
    setCashBalance(account.cashBalance || 0);
  }, [account.targetTotalAssets, account.cashBalance]);

  return (
    <div className="account-overview">
      <div className="metric-strip">
        <article className="strip-metric">
          <span>总资产</span>
          <strong>{formatCurrency(account.pnl.currentTotalAssets || account.targetTotalAssets)}</strong>
          <p>当前账本总资产</p>
        </article>
        <article className="strip-metric">
          <span>累计投入</span>
          <strong>{formatCurrency(account.pnl.initialTotalAssets)}</strong>
          <p>账户基线</p>
        </article>
        <article className="strip-metric">
          <span>已实现收益</span>
          <strong>{formatCurrency(account.pnl.realizedPnl)}</strong>
          <p>卖出已兑现</p>
        </article>
        <article className="strip-metric">
          <span>未实现收益</span>
          <strong>{formatCurrency(account.pnl.unrealizedPnl)}</strong>
          <p>当前持仓浮盈亏</p>
        </article>
        <article className="strip-metric">
          <span>总收益率</span>
          <strong>{formatPercent(account.pnl.totalReturnRate)}</strong>
          <p>基于累计投入</p>
        </article>
      </div>

      <div className="account-form">
        <div className="form-field">
          <label>目标总资产</label>
          <input type="number" value={targetTotalAssets} onChange={(event) => setTargetTotalAssets(Number(event.target.value || 0))} />
        </div>
        <div className="form-field">
          <label>现金余额</label>
          <input type="number" value={cashBalance} onChange={(event) => setCashBalance(Number(event.target.value || 0))} />
        </div>
        <button type="button" className="mock-button account-save" onClick={() => onSave({ target_total_assets: targetTotalAssets, cash_balance: cashBalance })}>
          保存账户口径
        </button>
      </div>
    </div>
  );
}
