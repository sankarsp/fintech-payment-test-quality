# Fintech Test Quality Report

Connect your test and bug tools. Get the reports a test lead shares every week,
and a clear go / no-go call, without building them by hand in Excel.

- **Reads from:** Jira, Tricentis qTest, OpenText ALM, or any CSV export (more coming)
- **One common model:** every tool's fields and values are mapped once, then every report works the same
- **Built for payments:** account and card numbers are masked before anything is stored
- **Reports:** weekly summary, trend, leakage, defect age, sprint, all 12 categories, source,
  interface, channel, application × priority, planned vs exploratory, epic / feature / story
  readiness, KPIs and go / no-go

The reports follow the article
[Sell me this defect](https://paymentconsultant.top/sell-me-this-defect/).
The demo data gives the same numbers as the article's sample reports.

## Run it (demo data)

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs, then try `/reports/weekly-summary` or `/reports/go-no-go`.

## Connect your tools

```bash
cp config/sources.example.yaml config/sources.yaml   # which tools
cp config/mapping.example.yaml config/mapping.yaml   # your field and value names
export FTQ_SOURCES=config/sources.yaml FTQ_MAPPING=config/mapping.yaml
export JIRA_EMAIL=... JIRA_API_TOKEN=...
uvicorn app.main:app
```

Then call `POST /sync` and check `GET /mapping/gaps` for any values that still need mapping.

## Tests

```bash
cd backend && pytest
```

Connector tests use mocked HTTP, so no real tool is needed.

See [docs/architecture.md](docs/architecture.md) for the design.
