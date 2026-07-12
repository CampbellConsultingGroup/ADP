/** Theme mode handling. Persists the user's choice and stamps data-theme on
 * <html>; "system" removes the attribute and lets prefers-color-scheme win. */
import { useCallback, useEffect, useState } from "react";

export type ThemeMode = "light" | "dark" | "system";

const KEY = "adp-theme";

export function getStoredTheme(): ThemeMode {
  const v = (typeof localStorage !== "undefined" && localStorage.getItem(KEY)) as ThemeMode | null;
  // All pages are migrated to theme tokens, so follow the OS preference by default.
  return v === "light" || v === "dark" || v === "system" ? v : "system";
}

export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  if (mode === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", mode);
}

/** Call once at app startup to apply the stored preference before first paint. */
export function initTheme(): void {
  applyTheme(getStoredTheme());
}

export function useTheme(): { mode: ThemeMode; setMode: (m: ThemeMode) => void; cycle: () => void } {
  const [mode, setModeState] = useState<ThemeMode>(getStoredTheme);

  useEffect(() => {
    applyTheme(mode);
  }, [mode]);

  const setMode = useCallback((m: ThemeMode) => {
    setModeState(m);
    try {
      localStorage.setItem(KEY, m);
    } catch {
      /* ignore storage failures */
    }
  }, []);

  // Toggle between light and dark (resolving "system" to its opposite of current).
  const cycle = useCallback(() => {
    const prefersDark =
      typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches;
    const effective = mode === "system" ? (prefersDark ? "dark" : "light") : mode;
    setMode(effective === "dark" ? "light" : "dark");
  }, [mode, setMode]);

  return { mode, setMode, cycle };
}
