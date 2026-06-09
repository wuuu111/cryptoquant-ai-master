import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentDecisionChain } from "./AgentDecisionChain";

describe("AgentDecisionChain", () => {
  it("renders each agent card with isolated copy blocks", () => {
    const { container } = render(
      <AgentDecisionChain
        steps={[
          {
            name: "FundSupervisorAgent",
            label: "Supervisor 裁决",
            summary: "LLM supervisor connected and routed to review.",
            status: "warning",
          },
        ]}
      />,
    );

    expect(screen.getByRole("heading", { name: "FundSupervisorAgent" })).toBeInTheDocument();
    expect(container.querySelector(".agent-step-copy")).not.toBeNull();
    expect(container.querySelector(".agent-step-name")).not.toBeNull();
  });
});
