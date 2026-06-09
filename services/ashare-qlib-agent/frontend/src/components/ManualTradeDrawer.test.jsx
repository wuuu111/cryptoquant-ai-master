import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ManualTradeDrawer } from "./ManualTradeDrawer";

describe("ManualTradeDrawer", () => {
  it("defaults to SELL for decrease suggestions", () => {
    render(
      <ManualTradeDrawer
        open
        seed={{
          symbol: "000001",
          fundName: "华夏成长混合",
          action: "DECREASE",
          deltaValue: -50000,
        }}
        onClose={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByRole("combobox")).toHaveValue("SELL");
  });

  it("renders as a dismissible dialog overlay", () => {
    let closed = 0;
    render(
      <ManualTradeDrawer
        open
        seed={null}
        onClose={() => {
          closed += 1;
        }}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByRole("dialog", { name: "手工记账" })).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("manual-trade-backdrop"));
    expect(closed).toBe(1);
  });
});
