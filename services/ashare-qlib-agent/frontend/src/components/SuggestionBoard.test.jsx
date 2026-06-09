import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SuggestionBoard } from "./SuggestionBoard";

describe("SuggestionBoard", () => {
  it("renders amount-first blocked suggestion cards", () => {
    render(
      <SuggestionBoard
        suggestions={[
          {
            symbol: "159915",
            fundName: "创业板 ETF",
            actionLabel: "增加",
            blocked: true,
            reason: "Purchase status is closed.",
            amountLabel: "+200,000",
            currentWeightLabel: "0.0%",
            targetWeightLabel: "20.0%",
            deltaWeightLabel: "+20.0%",
            deltaWeight: 0.2,
            tone: "blocked",
          },
        ]}
      />,
    );

    expect(screen.getByText("+200,000")).toBeInTheDocument();
    expect(screen.getByText("风险阻断")).toBeInTheDocument();
    expect(screen.getByText("创业板 ETF")).toBeInTheDocument();
  });

  it("shows applied suggestions as already booked", () => {
    render(
      <SuggestionBoard
        suggestions={[
          {
            symbol: "000001",
            fundName: "华夏成长混合",
            actionLabel: "增加",
            blocked: false,
            applied: true,
            reason: "Booked into local ledger.",
            amountLabel: "+100,000",
            currentWeightLabel: "0.0%",
            targetWeightLabel: "20.0%",
            deltaWeightLabel: "+20.0%",
            deltaWeight: 0.2,
            tone: "good",
          },
        ]}
      />,
    );

    expect(screen.getAllByText("已记账")).toHaveLength(2);
    expect(screen.queryByText("一键调仓")).not.toBeInTheDocument();
  });
});
