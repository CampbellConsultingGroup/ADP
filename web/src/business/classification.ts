import type { BadgeTone } from "../ui";

/** Business domain classification → semantic badge tone + label. */
export const CLASSIFICATION_TONE: Record<string, BadgeTone> = {
  strategic: "good",
  differentiating: "warn",
  commodity: "neutral",
};

export const CLASSIFICATION_LABEL: Record<string, string> = {
  strategic: "Strategic",
  differentiating: "Differentiating",
  commodity: "Commodity",
};

/** Capability tree level → wayfinding fg/bg tokens. */
export const LEVEL_STYLE: Record<number, { fg: string; bg: string }> = {
  1: { fg: "var(--accent)", bg: "var(--accent-wash)" },
  2: { fg: "var(--good)", bg: "var(--good-wash)" },
  3: { fg: "var(--biz)", bg: "var(--biz-wash)" },
};
