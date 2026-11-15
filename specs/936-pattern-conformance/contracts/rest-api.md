# REST Contract: adoptions, conformance and discovery (936)

Prefix `/api/v1/patterns`. Every literal route below is declared before `GET /{key}`.

| Method & path | Action | Request | Responses |
|---|---|---|---|
| `GET /adoptions` | — | `?pattern_key=&scope_type=&with_status=false` | 200 `{items: Adoption[], total}`. `status` is filled only when `with_status=true` (computed per caller) |
| `POST /adoptions` | WRITE_PATTERN | `AdoptionCreate` | 201 `Adoption`; 404 pattern/domain/version; 409 duplicate scope or name; 422 invalid scope, draft pin, invalid pins |
| `GET /adoptions/{id}` | — | | 200 `Adoption`, 404 |
| `PATCH /adoptions/{id}` | WRITE_PATTERN | `AdoptionUpdate` | 200, 404, 409 (name), 422 |
| `PUT /adoptions/{id}/members` | WRITE_PATTERN | `{member_ids: string[]}` | 200 `Adoption`; 422 if the adoption is not an application set or an id is unknown |
| `PUT /adoptions/{id}/pins` | WRITE_PATTERN | `{pins: PinIn[]}` | 200 `Adoption`; 422 `{detail: {message, reasons: string[]}}` |
| `DELETE /adoptions/{id}` | WRITE_PATTERN | | 204, 404 |
| `GET /adoptions/{id}/conformance` | — | | 200 `ConformanceReport`, 404 |
| `GET /adoptions/{id}/views/{view}` | — | `view` ∈ conformance\|transition; `?max_per_role=8` (2–50) | 200 `PatternViewResponse` (935); 422 for `transition` on a non-transition pattern |
| `GET /adoptions/{id}/candidates/{role_key}` | — | | 200 `ElementRef[]` (the role's element type, portfolio-wide, sorted by name), 404 |
| `GET /{key}/versions/{version}/discover` | — | | 200 `DiscoveryReport`; 404; 422 for a non-anti-pattern |
| `POST /evaluate` | WRITE_PATTERN (explicit rule) | `EvaluateRequest` | 200 `ConformanceReport` (`adoption_id: null`); 422 YAML issues `{detail: {message, issues}}` |

Log lines:
- `patterns.adoption.create|update|members|pins|delete id=%s pattern=%s scope=%s actor=%s`.

Frontend hooks (`web/src/api/patterns.ts`):
- `useAdoptions(filters)`, `useAdoption(id)`, `useConformance(id)`, `useAdoptionView(id, view)`, `useCandidates(id, role)`;
- `useCreateAdoption()`, `useUpdateAdoption(id)`, `useSetMembers(id)`, `useSetPins(id)`, `useDeleteAdoption(id)`;
- `useDiscovery(key, version)`, `useEvaluate()`.

All writes invalidate `["patterns", "adoptions"]`.
