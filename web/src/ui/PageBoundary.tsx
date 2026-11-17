import React, { Suspense } from "react";
import { QueryErrorResetBoundary } from "@tanstack/react-query";

/**
 * Error + loading boundary around the current page, inside the app shell (ADP-blp.30).
 *
 * The only boundary used to be the root one in main.tsx, above the shell. A page that threw --
 * most easily a suspense query such as useApplications() failing on Overview, the landing page --
 * replaced the whole app, navigation included, with "Something went wrong", and a reload landed
 * on the same failure. This keeps the failure inside the page area: the nav stays usable, and
 * "Try again" re-runs the failed queries without a full reload.
 *
 * Give it a `key` that changes with the view so that navigating away clears the error.
 */
interface BoundaryProps {
  children: React.ReactNode;
  onReset: () => void;
}

interface BoundaryState {
  error: Error | null;
}

class PageErrorBoundary extends React.Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error("Page failed to render:", error, info);
  }

  private retry = (): void => {
    this.props.onReset();
    this.setState({ error: null });
  };

  render(): React.ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="ui-page" role="alert" style={{ padding: "var(--space-6)" }}>
        <h2 style={{ margin: "0 0 var(--space-2)", fontSize: 18, color: "var(--ink)" }}>
          This page couldn&apos;t load
        </h2>
        <p style={{ margin: "0 0 var(--space-3)", color: "var(--ink-2)", maxWidth: 640 }}>
          Something went wrong while loading this page. The rest of the app still works, so you can
          try again or go to another page.
        </p>
        <pre
          style={{
            margin: "0 0 var(--space-4)",
            padding: "var(--space-3)",
            maxWidth: 720,
            overflow: "auto",
            borderRadius: "var(--radius-sm)",
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            color: "var(--ink-2)",
            fontSize: 12.5,
          }}
        >
          {error.message || String(error)}
        </pre>
        <button type="button" className="ui-btn ui-btn-primary" onClick={this.retry}>
          Try again
        </button>
      </div>
    );
  }
}

export function PageBoundary({ children }: { children: React.ReactNode }) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <PageErrorBoundary onReset={reset}>
          <Suspense
            fallback={
              <div role="status" style={{ padding: "var(--space-5)", color: "var(--ink-3)" }}>
                Loading…
              </div>
            }
          >
            {children}
          </Suspense>
        </PageErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  );
}

export default PageBoundary;
