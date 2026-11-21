# Geography reference data

| File | What | Used by |
| --- | --- | --- |
| `geographies.json` | UN M49 regions with ISO 3166-1 countries (940) | migration 048, `geodata.seed_v2` |
| `iso_3166-2.json.gz` | Pinned ISO 3166-2 subdivision list (code, name, type, parent), 5,046 rows | `geodata.subdivision`; the reference for adding a subdivision (949) |
| `regulatory_blocs.json` | EU and EEA dated memberships, plus the governed custom places | migration 060 |

Subdivisions are not bulk-loaded (epic ADP-bo1 decision, 2026-11-20). A subdivision is added on
demand, only with a code that exists in the snapshot, and takes its name from it.

`iso_3166-2.json.gz` is taken from iso-codes 4.20.1
(<https://salsa.debian.org/iso-codes-team/iso-codes>), which is licensed LGPL-2.1-or-later. The
file is redistributed unmodified apart from field selection and compression. To update it, take
`data/iso_3166-2.json` from a newer iso-codes release, rebuild the file the same way (sorted by
code; keys code, name, type, parent) and update `source` and `retrieved` inside it.

Membership dates in `regulatory_blocs.json` were checked against the sources listed in the file.
Changing a date in this file does not change a database that already ran migration 060: change it
through the API (Business -> Organization -> Geography) or in a new migration.
