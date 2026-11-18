import React from "react";
import { useLLMConfig, useUpdateLLMConfig, useAvailableModels, type LLMConfigUpdate } from "../api/config";
import { useCan } from "../auth/permissions";
import { Alert, Field, Loading } from "../ui/primitives";

/**
 * Which model each AI step uses (ADP-blp.13). A choice is stored on the server, so it applies to
 * everyone at once and survives a restart. The API key is not set here: it is a deploy-time
 * secret (Key Vault on Azure, the ADP_LLM_API_KEY entry in .env locally), and this screen only
 * reports whether one is configured.
 */
const STEPS: { setting: keyof LLMConfigUpdate; label: string }[] = [
  { setting: "extraction_model", label: "Extraction Model" },
  { setting: "recommendation_model", label: "Recommendation Model" },
  { setting: "validation_model", label: "Validation Model" },
];

export default function LLMSettings(): React.ReactElement {
  const { data: config, isLoading } = useLLMConfig();
  const { data: models } = useAvailableModels();
  const update = useUpdateLLMConfig();
  const canChange = useCan("manage_config");

  if (isLoading) return <Loading pad={16} />;

  const connected = config?.api_key_configured ?? false;
  const options = models?.models ?? [];

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>LLM Settings</h3>

      <div style={{ marginBottom: 14, padding: 10, background: "var(--surface-2)", borderRadius: 6 }}>
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 4 }}>Provider</div>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Anthropic</div>
        <div style={{ fontSize: 12, color: connected ? "var(--good)" : "var(--crit)", marginTop: 4 }}>
          ● {connected ? `Connected (${config?.provider})` : "API key not configured"}
        </div>
        <div style={{ fontSize: 11.5, color: "var(--ink-2)", marginTop: 6 }}>
          The API key is set when the platform is deployed, not on this screen.
          {!connected && " Until one is configured, AI steps return placeholder results."}
        </div>
      </div>

      {STEPS.map(({ setting, label }) => {
        const value = config?.[setting] ?? "claude-sonnet-4-6";
        return (
          <Field
            key={setting}
            label={label}
            hint={options.find((m) => m.id === value)?.description}
          >
            {(control) => (
              <select
                {...control}
                className="ui-select"
                value={value}
                disabled={!canChange.allowed || update.isPending}
                title={canChange.reason}
                onChange={(e) => update.mutate({ [setting]: e.target.value })}
              >
                {options.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} — {m.tier}
                  </option>
                ))}
              </select>
            )}
          </Field>
        );
      })}

      {update.isSuccess && <Alert tone="good">Saved. The choice applies to everyone.</Alert>}
      {update.isError && <Alert tone="crit">Could not save: {update.error.message}</Alert>}
    </div>
  );
}
