import React, { useEffect, useState } from "react";

export function ManualTradeDrawer({ open, seed, onSubmit, onClose }) {
  const [symbol, setSymbol] = useState("");
  const [fundName, setFundName] = useState("");
  const [side, setSide] = useState("BUY");
  const [amount, setAmount] = useState("");
  const [price, setPrice] = useState("");

  useEffect(() => {
    setSymbol(seed?.symbol || "");
    setFundName(seed?.fundName || "");
    setSide(seed?.action === "DECREASE" || seed?.actionLabel === "降低" ? "SELL" : "BUY");
    setAmount(seed?.deltaValue ? String(Math.abs(seed.deltaValue)) : "");
    setPrice("");
  }, [seed]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    function onKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="manual-modal-backdrop"
      data-testid="manual-trade-backdrop"
      onClick={onClose}
    >
      <div
        className="manual-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="manual-trade-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="manual-drawer-head">
          <h4 id="manual-trade-title">手工记账</h4>
          <button type="button" className="jump-button" onClick={onClose}>关闭</button>
        </div>
        <div className="manual-drawer-grid">
          <div className="form-field">
            <label>基金代码</label>
            <input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="如 000001" />
          </div>
          <div className="form-field">
            <label>基金名称</label>
            <input value={fundName} onChange={(event) => setFundName(event.target.value)} placeholder="可选" />
          </div>
          <div className="form-field">
            <label>方向</label>
            <select value={side} onChange={(event) => setSide(event.target.value)}>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>
          <div className="form-field">
            <label>金额</label>
            <input type="number" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="80000" />
          </div>
          <div className="form-field">
            <label>成交净值</label>
            <input type="number" value={price} onChange={(event) => setPrice(event.target.value)} placeholder="1.3280" />
          </div>
        </div>
        <div className="manual-drawer-actions">
          <button
            type="button"
            className="mock-button"
            onClick={() => onSubmit({
              symbol,
              fund_name: fundName,
              side,
              amount: Number(amount || 0),
              price: Number(price || 0),
            })}
          >
            记账
          </button>
        </div>
      </div>
    </div>
  );
}
