"""Report tests on the demo data. The expected numbers are the ones shown in
the article "Sell me this defect", so the article and the app always agree."""
from fastapi.testclient import TestClient

from app import reports as R
from app.connectors.demo import AS_OF, DemoConnector
from app.main import app
from app.mapping import Mapping
from app.masking import mask_text

DATA = DemoConnector({}, Mapping()).fetch()


def test_weekly_summary_matches_article():
    s = R.weekly_summary(DATA, AS_OF)
    assert s["tests"] == {"planned": 450, "run": 412, "passed": 389}
    assert (s["open_bugs"], s["open_critical"], s["open_high"]) == (50, 2, 6)
    assert s["leakage_pct"] == 3.0
    assert 5.5 <= s["reopen_pct"] <= 6.5
    assert s["oldest_open"]["days"] == 41 and s["oldest_open"]["owner_team"] == "Core banking team"
    r = s["readiness"]
    assert (r["stories_tested"], r["stories_total"]) == (34, 40)
    assert (r["features_ready"], r["features_total"]) == (5, 7)
    assert (r["epics_on_track"], r["epics_total"]) == (2, 3)
    assert r["at_risk_epics"] == ["Domestic wires"]


def test_breakdowns_match_article():
    assert [(x["name"], x["bugs"]) for x in R.by_category(DATA)][:4] == [
        ("Functional", 58), ("Data", 30), ("Environment", 24), ("Requirement", 22)]
    assert len(R.by_category(DATA)) == 12
    assert R.by_source(DATA)[0] == {"name": "Manual", "bugs": 90}
    assert R.by_interface(DATA)[0] == {"name": "Downstream", "bugs": 5}
    assert R.application_by_priority(DATA)[-1] == {"application": "Total", "P1-P2": 25, "P3-P4": 173}
    assert R.planned_vs_exploratory(DATA) == {"planned": 140, "exploratory": 58}


def test_go_no_go_is_no_go_with_open_criticals():
    result = R.go_no_go(DATA, as_of=AS_OF)
    assert result["decision"] == "No-go"
    assert set(result["not_ready"]) == {"Wire approvals", "Scheduled wires"}
    relaxed = R.go_no_go(DATA, gates={"max_open_critical": 5, "max_open_high": 10,
                                      "target_pass_rate_pct": 90}, as_of=AS_OF)
    assert relaxed["decision"] == "Go"


def test_masking():
    assert mask_text("acct 123456789012 failed") == "acct ********9012 failed"
    assert mask_text("card 4111-1111-1111-1111") == "card ************1111"
    assert mask_text("mail jane.doe@bank.com") == "mail j***@bank.com"
    assert mask_text("IBAN DE89370400440532013000 rejected").startswith("IBAN DE89****")


def test_api_end_to_end():
    with TestClient(app) as client:
        assert client.get("/health").json()["defects"] == 198
        assert "go-no-go" in client.get("/reports").json()
        assert client.get("/reports/category").status_code == 200
        assert client.get("/reports/go-no-go", params={"as_of": AS_OF.isoformat()}).json()["decision"] == "No-go"
        assert client.get("/reports/nope").status_code == 404
        assert client.get("/mapping/gaps").json() == {}
