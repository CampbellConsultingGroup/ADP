# Quickstart: Mapping Rationale (943)

Run against a local backend on :8001 with migration `051` applied. All scratch data is removed at the end.

```bash
API=http://localhost:8001/api/v1
AC=$API/application-capabilities
```

1. **Classify an existing realization (US1).** Pick an application capability with at least one realization, then:
   ```bash
   curl -s -X PATCH $AC/$AC_ID/applications/$APP_ID -H 'content-type: application/json' \
     -d '{"rationale":"target"}' | jq '.realized_by'
   ```
   The entry shows `"rationale": "target"`, `"geography": null`.
2. **Scope it to a region, then clear it.** Set `{"geography_id":"<Americas id>"}`, then `{"geography_id":null}`. The geography goes back to null and the rationale is kept.
3. **Refusals.** `{"geography_id":"geo-001"}` (Global) gives 422 "No geography already means everywhere". `{"rationale":"maybe"}` gives 422. An unknown link gives 404.
4. **Overlaps (US2).** `GET $AC/analysis/findings`. Then:
   - an overlap whose mappings are all unclassified shows `status: needs_attention` with an `unclassified` reason;
   - mark one application target and the other tactical, and it becomes `explained`;
   - mark both target with no geography, and it shows `competing_targets`;
   - scope them to Europe and the Americas, and it's `explained` again.
5. **Redundant (US3).** Mark a mapping redundant on an application with TIME Invest. `redundant[]` lists it under its business L3, with `hint: "TIME says Invest"`.
6. **UI.** In Applications → Capabilities, open the capability. Choosing a rationale or geography on a realization row saves at once. The Overlaps tab shows Needs attention and Explained, and the Redundant tab lists the mapping. On Governance → Architecture Health, the Overlaps tile counts only the overlaps that need attention.
7. **Clean up.** Restore every rationale and geography you changed to null.
