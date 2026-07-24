import React from "react";

/**
 * Top-level React error boundary (ADP-cm9 / ADP-iuc).
 *
 * Without this, any unhandled render error -- e.g. a component consuming an API
 * query that failed (a 401 after login, the backend being down) -- unmounts the
 * whole tree, leaving an empty #root and the dark body background = a black
 * screen with no signal. This catches it and shows what actually went wrong,
 * plus a reload, so failures are diagnosable instead of invisible.
 */
interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // Leave a trace for diagnosis (and, later, telemetry).
    console.error("Unhandled UI error:", error, info);
  }

  render(): React.ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          padding: "2rem",
          fontFamily: "system-ui, Arial, sans-serif",
          background: "var(--bg, #0a0f16)",
          color: "var(--text, #e6edf6)",
          textAlign: "center",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.4rem" }}>Something went wrong</h1>
        <p style={{ margin: 0, maxWidth: 640, opacity: 0.85 }}>
          The application hit an unexpected error and couldn&apos;t render. This is
          usually a temporary problem loading your data.
        </p>
        <pre
          style={{
            maxWidth: 720,
            overflow: "auto",
            padding: "0.75rem 1rem",
            borderRadius: 8,
            background: "rgba(127,127,127,0.15)",
            fontSize: "0.85rem",
            textAlign: "left",
          }}
        >
          {error.message || String(error)}
        </pre>
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: 8,
            border: "1px solid rgba(127,127,127,0.5)",
            background: "#2874A6",
            color: "#fff",
            cursor: "pointer",
            fontSize: "0.95rem",
          }}
        >
          Reload
        </button>
      </div>
    );
  }
}

export default ErrorBoundary;
