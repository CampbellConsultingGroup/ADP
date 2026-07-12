/** Shared inline icon set. Stroke-based, inherits color via currentColor. */
import React from "react";

export const ICONS: Record<string, React.ReactNode> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  layers: <><polygon points="12,3 21,8 12,13 3,8" /><path d="M3 12l9 5 9-5M3 16l9 5 9-5" /></>,
  biz: <><path d="M4 20V9l8-5 8 5v11" /><path d="M9 20v-5h6v5" /><path d="M4 12h16" /></>,
  ent: <><rect x="3" y="4" width="6" height="6" rx="1" /><rect x="15" y="4" width="6" height="6" rx="1" /><rect x="9" y="14" width="6" height="6" rx="1" /><path d="M6 10v2h12v-2M12 12v2" /></>,
  sol: <><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" /><path d="M12 3v9l8 4.5M12 12L4 16.5" /></>,
  tec: <><path d="M6 8l-3 4 3 4M18 8l3 4-3 4M14 5l-4 14" /></>,
  stream: <><path d="M3 7h11l4 5-4 5H3" /><path d="M3 12h9" /></>,
  link: <><path d="M9 12h6" /><path d="M10 8H8a4 4 0 000 8h2M14 8h2a4 4 0 010 8h-2" /></>,
  plug: <><path d="M9 3v6M15 3v6M6 9h12v3a6 6 0 01-12 0zM12 18v3" /></>,
  chart: <><path d="M4 20V4M4 20h16" /><rect x="7" y="12" width="3" height="5" /><rect x="12" y="8" width="3" height="9" /><rect x="17" y="5" width="3" height="12" /></>,
  shield: <><path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9.5 12l2 2 3.5-4" /></>,
  book: <><path d="M4 5a2 2 0 012-2h12v16H6a2 2 0 00-2 2z" /><path d="M4 19a2 2 0 012-2h12" /></>,
  tags: <><path d="M4 4h8l8 8-8 8-8-8z" /><circle cx="8.5" cy="8.5" r="1.4" /></>,
  image: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.6" /><path d="M4 17l5-5 4 4 3-3 4 4" /></>,
  inbox: <><path d="M4 13l2-8h12l2 8v6H4z" /><path d="M4 13h5l1 2h4l1-2h5" /></>,
  spark: <><path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" /></>,
  check: <><path d="M4 12l5 5L20 6" /><circle cx="12" cy="12" r="9" opacity=".35" /></>,
  cycle: <><path d="M4 12a8 8 0 0113-6l3 2M20 12a8 8 0 01-13 6l-3-2" /><path d="M20 4v4h-4M4 20v-4h4" /></>,
  doc: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></>,
  go: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  chevronDown: <><path d="M6 9l6 6 6-6" /></>,
  compass2: <><circle cx="12" cy="12" r="9" /></>,
  compass: <><circle cx="12" cy="12" r="9" /><polygon points="16,8 13,13 8,16 11,11" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></>,
  bell: <><path d="M6 9a6 6 0 0112 0c0 5 2 6 2 6H4s2-1 2-6z" /><path d="M10 20a2 2 0 004 0" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" /></>,
  moon: <><path d="M20 14a8 8 0 01-10-10 8 8 0 1010 10z" /></>,
  target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="1" /></>,
};

export type IconName = keyof typeof ICONS;

export function Icon({
  name,
  size = 20,
  className,
  style,
}: {
  name: string;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}): React.ReactElement {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      {ICONS[name] ?? null}
    </svg>
  );
}
