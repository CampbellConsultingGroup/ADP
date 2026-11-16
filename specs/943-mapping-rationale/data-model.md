# Data Model: Mapping Rationale (943)

## Changed table: `app_capability_realizations` (migration `051`, `down_revision = "050"`)

| Column | Type | Rule |
|---|---|---|
| app_capability_id | String(36) | PK, FK → application_capabilities CASCADE (unchanged) |
| app_id | String(36) | PK, FK → applications CASCADE (unchanged) |
| created_at | timestamptz | unchanged |
| **rationale** | TEXT NULL | CHECK `ck_app_cap_realization_rationale`: `rationale IN ('target','tactical','transitional','redundant')`. NULL = unclassified |
| **geography_id** | String(36) NULL | FK `fk_app_cap_realization_geography` → geographies.id **ON DELETE SET NULL**; index `ix_app_cap_realizations_geography_id`. NULL = everywhere |

Migration notes:
- **Upgrade** adds the two columns, the CHECK, the FK and the index, with no data change.
- **Downgrade** drops them, in reverse order.
- **In SQLAlchemy metadata** (`adp.application.store._app_cap_realizations`), `geography_id` is a plain column with no `ForeignKey` (research R1).

Validation, in the store, as a 422 naming the rule:
- the rationale is one of the four values or null. Pydantic `Literal` enforces it first; the CHECK is a backstop;
- the geography must exist ("Geography … not found");
- the geography must not be level 1 ("No geography already means everywhere").

## Derived (never stored)

```text
Realization            (snapshot)  rationale | None, geography_id | None

Mapping                (API)       via: CapRef (application capability)
                                    rationale | None, geography: GeoRef | None, hint: str | None

AppVia                 (API, +)    id, name, via[] (unchanged), mappings: Mapping[]

OverlapReason          (API)       code: unclassified | redundant | no_target | competing_targets
                                    application_ids: [str]   (the applications concerned, by name)

OverlapEntry           (API, +)    business, applications[], status: needs_attention | explained,
                                    reasons: OverlapReason[]

RedundantEntry         (API)       application: {id, name, time_classification, r_strategy},
                                    app_capability: CapRef, geography: GeoRef | None, hint | None

RedundantGroup         (API)       business: LinkedCapRef | None, entries: RedundantEntry[]

CapabilityFindings     (API, +)    overlaps, gaps, shared (unchanged), redundant: RedundantGroup[]

AppRef                 (API, +)    id, name, rationale | None, geography: GeoRef | None, hint | None
```

`GeoRef` is `{id, name, code | None}`.

## Rules

- **Overlap membership** is unchanged from 938: a business L3 with two or more non-retired applications, reached through application capabilities.
- **Mappings of an overlap**: every (application, application capability) pair that reaches the L3, for non-retired applications.
- **Reasons** (research R5):
  - `unclassified`: some mapping's rationale is null;
  - `redundant`: some mapping is redundant;
  - `no_target`: only when nothing is unclassified, nothing is redundant, and no mapping is target;
  - `competing_targets`: two target mappings of **different** applications have overlapping scope. That means both have no geography, or they have equal geographies, or one contains the other in the geography tree. A geography id that isn't in the index counts as none.
- **Status**: `needs_attention` if there's any reason, else `explained`.
- **Hint**:
  - target with TIME ∈ {Eliminate, Migrate} gives "TIME says <value>";
  - redundant with TIME = Invest gives "TIME says Invest";
  - anything else gives none.
- **Redundant groups**:
  - only non-retired applications;
  - each redundant mapping appears under every business L3 its application capability reaches. If it reaches none, it goes in the `business: null` group, which comes last.
