import { beforeEach, describe, expect, it, vi } from "vitest";
import { installChunkRecovery } from "./chunkRecovery";

describe("route chunk recovery", () => {
  beforeEach(() => sessionStorage.clear());

  it("reloads once after a stale lazy chunk and prevents a reload loop", () => {
    const reload = vi.fn();
    const remove = installChunkRecovery(reload, () => 100_000);
    const first = new Event("vite:preloadError", { cancelable: true });
    window.dispatchEvent(first);
    const repeated = new Event("vite:preloadError", { cancelable: true });
    window.dispatchEvent(repeated);
    remove();

    expect(first.defaultPrevented).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(repeated.defaultPrevented).toBe(false);
  });
});
