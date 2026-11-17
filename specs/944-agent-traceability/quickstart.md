# Quickstart: Agent Traceability (944)

Run against a local backend on :8001 with migration `052` applied. Every bit of scratch data created here is removed at the end.

```bash
API=http://localhost:8001/api/v1
AG=$API/agentic
```

1. **Automates (US1).** Pick an agent (`GET $AG/agents`) and a business L3 capability. Then:
   ```bash
   curl -s -X POST $AG/agents/$AGENT/automates/capabilities -H 'content-type: application/json' \
     -d "{\"capability_id\":\"$L3\"}"
   curl -s $AG/capabilities/$L3/agents
   ```
   The agent appears in both responses. Then check the refusals:
   - an L2 capability gives 422 "Agents automate business capabilities at L3 only";
   - repeating the POST gives 409;
   - an unknown id gives 404.
2. **Stages and activities.** Link a value stream stage and a value chain activity the same way, then check `GET $AG/value-stream-stages/$STAGE/agents`.
3. **Compliance (US2).** Map two controls to the agent:
   ```bash
   curl -s -X PUT $API/compliance/controls/$C1/mappings/agents/$AGENT -H 'content-type: application/json' \
     -d '{"compliance_status":"compliant"}'
   ```
   Map `$C2` as `non_compliant`. Then:
   - `GET $API/compliance/agents/$AGENT/mappings` shows two items and `status: non_compliant`;
   - the framework roll-up's counts go up by one.
4. **Separate from the solution.** The agentic application's Regulatory Compliance tab and its application mappings are unchanged by the agent's mappings.
5. **Risk (US3).** Set the agent to autonomy 4 with human approval `none` (PATCH). Then:
   - `GET $AG/solutions/$APP/agents` shows `solution_risk.band: high`, naming the agent;
   - set approval to `always` and the classification to `internal`, and the band drops to `medium`;
   - retire the agent, and it no longer counts towards the band.
6. **UI.**
   - **Agents → the agent:** the Automates section adds a capability, stage or activity as soon as one is chosen. Compliance and Agentic risk show beside it.
   - **The agentic application's Agents tab:** shows the solution band, plus a band and compliance status for each agent.
   - **Business → Capabilities:** the L3 row's "Automated by agents" expander lists the agent, and choosing it opens the agent.
   - **Compliance:** on a control, an agent can be picked as a mapping target, and agent rows show no initiative line.
7. **Clean up.**
   - Remove the links and mappings you added.
   - Restore the agent's autonomy, approval, classification and lifecycle.
