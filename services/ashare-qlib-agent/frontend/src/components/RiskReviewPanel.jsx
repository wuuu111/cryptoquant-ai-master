import React from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { EmptyState } from "./EmptyState";

export function RiskReviewPanel({ review }) {
  if (!review.summary && !review.riskNotes?.length) {
    return (
      <EmptyState
        title="当前还没有审查结论"
        detail="等待新的基金周期，这里会展示复核摘要和风险提示。"
      />
    );
  }

  return (
    <div className="risk-review">
      <p className="review-summary">{review.summary}</p>
      <div className="risk-list">
        {(review.riskNotes || []).length ? (
          review.riskNotes.map((note, index) => (
            <div key={`${note}-${index}`} className="risk-item">
              <AlertTriangle size={14} />
              <span>{note}</span>
            </div>
          ))
        ) : (
          <div className="risk-item good">
            <CheckCircle2 size={14} />
            <span>本轮没有新增风险提示。</span>
          </div>
        )}
      </div>
    </div>
  );
}
