import { describe, expect, it, vi } from "vitest";

import { fetchHealth, getDefaultApiBase } from "./api";

describe("api base resolution", () => {
  it("defaults to the reverse-proxy api path", () => {
    expect(getDefaultApiBase()).toBe("/api");
  });

  it("tries the reverse-proxy path before falling back to localhost", async () => {
    const setActiveApiBase = vi.fn();
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("proxy unavailable"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true }),
      });

    vi.stubGlobal("fetch", fetchMock);

    const payload = await fetchHealth("", setActiveApiBase);

    expect(payload).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/health",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8710/health",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(setActiveApiBase).toHaveBeenCalledWith("http://127.0.0.1:8710");
    vi.unstubAllGlobals();
  });
});
