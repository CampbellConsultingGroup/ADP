import { useEffect, useRef, useState } from "react";

export interface LinkFeedback {
  /** Transient confirmation text, or null when nothing to show. */
  message: string | null;
  showLinked: (name: string) => void;
  showRemoved: (name: string) => void;
}

/** Transient "Linked X" / "Removed X" confirmation shared by
 * ObjectiveCapabilityLinkEditor and its four siblings (ValueStream/Design/
 * Application/Initiative). Each Link/Remove button already persists
 * immediately on click -- there is no separate Save step, and none is
 * needed -- but nothing previously confirmed that to the user, which read as
 * "there's no way to save" (reported live, 2026-08-14). Extracted as one
 * shared hook rather than duplicated five times, matching this session's own
 * `checkMetricFields` precedent for de-duplicating logic identical across
 * multiple near-verbatim editor components.
 *
 * Auto-clears after a few seconds so the confirmation doesn't linger
 * indefinitely once the user has moved on. */
export function useLinkFeedback(): LinkFeedback {
  const [message, setMessage] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    },
    [],
  );

  function show(text: string) {
    setMessage(text);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setMessage(null), 3000);
  }

  return {
    message,
    showLinked: (name) => show(`✓ Linked "${name}"`),
    showRemoved: (name) => show(`Removed "${name}"`),
  };
}
