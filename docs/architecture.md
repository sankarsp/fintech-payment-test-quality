# Architecture

```
 Jira ─┐
 qTest ─┤   connectors        common model        reports               dashboard
 ALM ──┼──► (read only) ───► Defect, TestRun ───► weekly summary  ───► React UI
 CSV ──┤      + mapping        + masking           trend, leakage       PDF / email
 Demo ─┘                                          go / no-go           audit export
```

## 1. Connectors (read only)

| Tool | API used | Auth |
|---|---|---|
| Jira Cloud | `GET /rest/api/3/search/jql` (pages with `nextPageToken`) | email + API token |
| Tricentis qTest | `POST /api/v3/projects/{id}/search` for `defects` and `test-runs` | bearer token |
| OpenText ALM | `/qcbin/rest/domains/{d}/projects/{p}/defects` and `/runs` | API key (`/rest/oauth2/login`) or basic sign-in |
| CSV | any export, column names set in the mapping | none |
| Demo | generated sample data | none |

Connectors never write back to the tool. Next connectors: Azure DevOps, TestRail,
Xray / Zephyr (test runs inside Jira), GitHub Issues.

## 2. Common data model

Every report reads only `Defect` and `TestRun` (`backend/app/model.py`). This is
what lets one set of reports work for every tool.

## 3. Mapping

Each client maps their fields and values once (`config/mapping.example.yaml`).
Common names are built in. Anything not recognised is kept in
`raw_unmapped` and listed at `GET /mapping/gaps`; that list drives the mapping
screen (and later, AI suggestions for each gap, which a person approves).

## 4. Masking

Card numbers (Luhn checked), account numbers, IBANs and emails are masked when
the data comes in, before it is stored or shown.

## 5. Reports

| Report | Endpoint |
|---|---|
| Weekly test summary (tests, open bugs, leakage, reopen, oldest bug, epics / features / stories) | `/reports/weekly-summary` |
| Weekly trend (opened, closed, open at end of week) | `/reports/trend` |
| Leakage by test level | `/reports/leakage` |
| Defect age | `/reports/age` |
| Bugs per sprint | `/reports/sprint` |
| Category (all 12) | `/reports/category` |
| Source (manual, automation, performance, security, compliance, production) | `/reports/source` |
| Interface (upstream, downstream, external, legacy) | `/reports/interface` |
| Channel | `/reports/channel` |
| Application × priority | `/reports/application-priority` |
| Planned vs exploratory | `/reports/planned-vs-exploratory` |
| Epic / feature / story readiness | `/reports/readiness` |
| KPIs and go / no-go | `/reports/go-no-go` |

Go / no-go uses hard gates (any miss = No-go) and soft gates (any miss = Go with
conditions). The tool recommends; the release owner decides.

## Still to build

- React dashboard on top of these endpoints
- Postgres store and one schema per client
- Scheduled sync, weekly PDF / email
- Audit trail for go / no-go decisions
- AWS deployment
