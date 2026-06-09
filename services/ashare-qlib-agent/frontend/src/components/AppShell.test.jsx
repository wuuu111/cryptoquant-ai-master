import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("switches navigation and reflects refresh state", () => {
    const onSelectPage = vi.fn();
    const onRefresh = vi.fn();

    render(
      <AppShell
        activePage="today"
        onSelectPage={onSelectPage}
        onRefresh={onRefresh}
        refreshing
        activeApiBase="http://127.0.0.1:8710"
        lastUpdated="2026-06-04 18:00:00"
        health={{ ok: true, databaseEnabled: true, schedulerEnabled: false }}
        actionMessage=""
      >
        <div>workspace</div>
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: /我的基金/i }));
    expect(onSelectPage).toHaveBeenCalledWith("portfolio");
    expect(screen.getByRole("button", { name: /刷新中/i })).toBeDisabled();
  });
});
