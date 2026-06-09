import React from "react";

export function EmptyState({ title, detail, action = null }) {
  return (
    <div className="empty-state-panel">
      <p className="eyebrow">No Data Yet</p>
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  );
}
