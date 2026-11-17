import React, { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import { Icon } from "./Icon";
import { ModalOverlay } from "./ModalOverlay";

/**
 * Global search (ADP-blp.56). The top bar showed a "Search… ⌘K" box that was only a picture of
 * one: no input, no handler, no shortcut. This is the real thing, over the platform's existing
 * hybrid search index (GET /api/v1/search). ⌘K / Ctrl+K opens it from anywhere; arrow keys and
 * Enter pick a result; the app decides where each kind of result opens.
 */
export interface SearchHit {
  entity_type: string;
  entity_id: string;
  text: string;
  score: number;
}

// Every indexed type, with the label shown beside a result.
export const SEARCH_TYPE_LABELS: Record<string, string> = {
  business_capability: "Business capability",
  application: "Application",
  application_capability: "Application capability",
  technical_capability: "Technical capability",
  agent: "Agent",
  value_stream: "Value stream",
  value_stream_stage: "Value stream stage",
  value_chain: "Value chain",
  value_chain_activity: "Value chain activity",
  business_domain: "Business domain",
  org_unit: "Org unit",
};

const MIN_QUERY = 2;

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/** The first line of the indexed text is the entity's name (path for nested ones). */
function titleOf(hit: SearchHit): string {
  const firstLine = hit.text.split("\n")[0].trim();
  return firstLine.length > 90 ? `${firstLine.slice(0, 90)}…` : firstLine;
}

interface PaletteProps {
  onClose: () => void;
  onOpenResult: (hit: SearchHit) => void;
}

export function SearchPalette({ onClose, onOpenResult }: PaletteProps): React.ReactElement {
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const query = useDebounced(text.trim(), 200);
  const enabled = query.length >= MIN_QUERY;
  const types = useMemo(() => Object.keys(SEARCH_TYPE_LABELS).join(","), []);

  const { data, isFetching, isError } = useQuery<{ hits: SearchHit[] }>({
    queryKey: ["global-search", query],
    queryFn: () =>
      apiGet(`/api/v1/search?q=${encodeURIComponent(query)}&limit=12&entity_types=${types}`),
    enabled,
    staleTime: 60_000,
  });
  const hits = enabled ? (data?.hits ?? []) : [];
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => setActive(0), [query]);

  function choose(hit: SearchHit) {
    onOpenResult(hit);
    onClose();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (hits.length === 0) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + hits.length) % hits.length);
    } else if (event.key === "Enter" && hits[active]) {
      event.preventDefault();
      choose(hits[active]);
    }
  }

  let status: string | null = null;
  if (!enabled) status = "Type at least two characters to search capabilities, applications, agents and more.";
  else if (isError) status = "Search is unavailable right now.";
  else if (isFetching && hits.length === 0) status = "Searching…";
  else if (hits.length === 0) status = `No results for “${query}”.`;

  return (
    <ModalOverlay label="Search" onClose={onClose} style={{ alignItems: "flex-start", paddingTop: "12vh" }}>
      <div className="ui-palette">
        <div className="ui-palette-input">
          <Icon name="search" size={16} />
          <input
            autoFocus
            role="combobox"
            aria-label="Search"
            aria-expanded={hits.length > 0}
            aria-controls="search-palette-results"
            aria-activedescendant={hits[active] ? `search-hit-${active}` : undefined}
            placeholder="Search capabilities, applications, agents…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <span className="k">Esc</span>
        </div>
        {status && <div className="ui-palette-status" role="status">{status}</div>}
        {hits.length > 0 && (
          <ul id="search-palette-results" role="listbox" ref={listRef} className="ui-palette-list">
            {hits.map((hit, index) => (
              // Mouse users click; keyboard users use the input's arrow keys and Enter.
              // eslint-disable-next-line jsx-a11y/click-events-have-key-events
              <li
                key={`${hit.entity_type}:${hit.entity_id}`}
                id={`search-hit-${index}`}
                role="option"
                aria-selected={index === active}
                className={index === active ? "active" : undefined}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(hit)}
              >
                <span className="t">{titleOf(hit)}</span>
                <span className="ty">{SEARCH_TYPE_LABELS[hit.entity_type] ?? hit.entity_type}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </ModalOverlay>
  );
}

/** The top-bar search button plus the ⌘K / Ctrl+K shortcut. */
export function SearchLauncher({ onOpenResult }: { onOpenResult?: (hit: SearchHit) => void }): React.ReactElement {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <button type="button" className="shell-search" onClick={() => setOpen(true)} aria-label="Search">
        <Icon name="search" size={15} /> Search… <span className="k">⌘K</span>
      </button>
      {open &&
        // In a portal: the top bar's backdrop-filter makes it the containing block for
        // position: fixed, which would confine the overlay to the bar.
        createPortal(
          <SearchPalette onClose={() => setOpen(false)} onOpenResult={(hit) => onOpenResult?.(hit)} />,
          document.body,
        )}
    </>
  );
}
