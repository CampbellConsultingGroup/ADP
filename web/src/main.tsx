import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import AuthProvider from "./auth/AuthProvider";
import App from "./App";
import "./ui/tokens.css";
import "./ui/ui.css";
import { initTheme } from "./ui/theme";

initTheme();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <ReactFlowProvider>
          <App />
        </ReactFlowProvider>
      </QueryClientProvider>
    </AuthProvider>
  </React.StrictMode>,
);
