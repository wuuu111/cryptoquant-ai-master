import React from "react";
import { EmptyState } from "./EmptyState";

export function AgentTimeline({ trace, events, messages }) {
  const hasContent = trace.length || events.length || messages.length;

  if (!hasContent) {
    return (
      <EmptyState
        title="协作时间线为空"
        detail="新的基金周期会把 agent trace、协作事件和摘要消息都写到这里。"
      />
    );
  }

  return (
    <div className="dialogue-board">
      {(trace || []).map((item, index) => (
        <article key={`${item.name}-${index}`} className={`dialogue-bubble ${item.status}`}>
          <div className="dialogue-label">
            <strong>{item.label}</strong>
            <span>{item.role || item.name}</span>
          </div>
          <p>{item.summary}</p>
        </article>
      ))}
      {(events || []).map((item, index) => (
        <article key={`${item.agent}-${item.kind}-${index}`} className={`dialogue-bubble event ${item.severity || "info"}`}>
          <div className="dialogue-label">
            <strong>{item.label}</strong>
            <span>{item.kind}</span>
          </div>
          <p>{item.summary}</p>
        </article>
      ))}
      {(messages || []).map((item, index) => (
        <article key={`${item.agent_name}-${index}`} className="dialogue-bubble message info">
          <div className="dialogue-label">
            <strong>{item.agent_name}</strong>
            <span>summary</span>
          </div>
          <p>{item.summary || "暂无摘要。"}</p>
        </article>
      ))}
    </div>
  );
}
