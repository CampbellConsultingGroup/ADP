import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useLinkFeedback } from "./useLinkFeedback";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useLinkFeedback", () => {
  it("starts with no message", () => {
    const { result } = renderHook(() => useLinkFeedback());
    expect(result.current.message).toBeNull();
  });

  it("shows a confirmation message when showLinked is called", () => {
    const { result } = renderHook(() => useLinkFeedback());
    act(() => result.current.showLinked("Risk Assessment"));
    expect(result.current.message).toContain("Risk Assessment");
    expect(result.current.message).toContain("Linked");
  });

  it("shows a different message when showRemoved is called", () => {
    const { result } = renderHook(() => useLinkFeedback());
    act(() => result.current.showRemoved("Risk Assessment"));
    expect(result.current.message).toContain("Removed");
    expect(result.current.message).toContain("Risk Assessment");
  });

  it("auto-clears the message after a few seconds", () => {
    const { result } = renderHook(() => useLinkFeedback());
    act(() => result.current.showLinked("Risk Assessment"));
    expect(result.current.message).not.toBeNull();

    act(() => vi.advanceTimersByTime(3000));

    expect(result.current.message).toBeNull();
  });

  it("resets the auto-clear timer when a second message arrives before the first clears", () => {
    const { result } = renderHook(() => useLinkFeedback());
    act(() => result.current.showLinked("A"));
    act(() => vi.advanceTimersByTime(2000));
    act(() => result.current.showLinked("B"));
    act(() => vi.advanceTimersByTime(2000));

    // 4s of real time have passed, but only 2s since the second message --
    // it must still be showing (not cleared by the first message's timer).
    expect(result.current.message).toContain("B");
  });
});
