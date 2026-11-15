"""Connector tests with mocked HTTP: no real Jira, qTest or ALM needed."""
import json

import httpx

from app.connectors.alm import AlmConnector
from app.connectors.jira import JiraConnector
from app.connectors.qtest import QTestConnector
from app.mapping import Mapping
from app.model import Category, Severity, Status

MAPPING = Mapping({
    "tools": {
        "jira": {"fields": {"severity": "customfield_10050", "category": "label:cat-",
                            "channel": "component"},
                 "values": {"severity": {"Sev 1 - Outage": "S1"}}},
        "alm": {"fields": {"category": "user-03"}},
    }
})


def test_jira_pages_and_maps_values():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path == "/rest/api/3/search/jql"
        assert request.headers["authorization"].startswith("Basic ")
        if "nextPageToken" not in request.url.params:
            return httpx.Response(200, json={"issues": [{
                "key": "PAY-1",
                "fields": {"summary": "Card 4111 1111 1111 1111 declined", "status": {"name": "In Progress"},
                           "priority": {"name": "Highest"}, "customfield_10050": {"value": "Sev 1 - Outage"},
                           "labels": ["cat-data", "team-x"], "components": [{"name": "Mobile"}],
                           "created": "2026-11-01T10:00:00.000+0000", "resolutiondate": None}}],
                "nextPageToken": "abc", "isLast": False})
        return httpx.Response(200, json={"issues": [{
            "key": "PAY-2", "fields": {"summary": "Typo", "status": {"name": "Weird Custom State"},
                                       "priority": {"name": "Low"}, "labels": [], "components": [],
                                       "created": "2026-11-02T10:00:00.000+0000"}}], "isLast": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    conn = JiraConnector({"base_url": "https://x.atlassian.net", "email": "a@b.c", "api_token": "t"},
                         MAPPING, client)
    data = conn.fetch()
    assert len(calls) == 2
    first, second = data.defects
    assert first.severity == Severity.S1 and first.status == Status.OPEN
    assert first.category == Category.DATA and first.channel.value == "Mobile app"
    assert "4111 1111 1111 1111" not in first.title and first.title.endswith("************1111 declined")
    assert second.raw_unmapped == {"status": "Weird Custom State"}


def test_qtest_reads_properties_and_runs():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer tok"
        if body["object_type"] == "defects":
            return httpx.Response(200, json={"items": [{
                "id": 9, "pid": "DF-9", "created_date": "2026-11-03T08:00:00Z",
                "properties": [{"field_name": "Summary", "field_value": "Wire cut-off wrong"},
                               {"field_name": "Severity", "field_value_name": "2-High"},
                               {"field_name": "Status", "field_value_name": "Retest"},
                               {"field_name": "Type", "field_value_name": "Functional"},
                               {"field_name": "Test Type", "field_value_name": "Exploratory"}]}]})
        return httpx.Response(200, json={"items": [{
            "id": 1, "pid": "TR-1", "properties": [{"field_name": "Status", "field_value_name": "Passed"},
                                                  {"field_name": "Test Level", "field_value_name": "SIT"}]}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    data = QTestConnector({"base_url": "https://q.qtestnet.com", "token": "tok", "project_id": 1},
                          Mapping(), client).fetch()
    d = data.defects[0]
    assert (d.key, d.severity, d.status, d.exploratory) == ("DF-9", Severity.S2, Status.RETEST, True)
    assert data.runs[0].status == "Passed" and data.runs[0].level.value == "SIT"


def test_alm_signs_in_and_pages():
    def f(name, value):
        return {"Name": name, "values": [{"value": value}] if value is not None else []}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/rest/oauth2/login"):
            return httpx.Response(200, headers={"set-cookie": "LWSSO_COOKIE_KEY=abc; Path=/"})
        if path.endswith("/defects"):
            return httpx.Response(200, json={"TotalResults": 1, "entities": [{"Fields": [
                f("id", "77"), f("name", "Payee name truncated"), f("status", "Closed"),
                f("severity", "3-Medium"), f("priority", "2-High"), f("user-03", "Data"),
                f("creation-time", "2026-10-20"), f("closing-date", "2026-10-25")]}]})
        if path.endswith("/runs"):
            return httpx.Response(200, json={"TotalResults": 0, "entities": []})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    data = AlmConnector({"base_url": "https://alm.example.com/qcbin", "domain": "D", "project": "P",
                         "client_id": "id", "client_secret": "s"}, MAPPING, client).fetch()
    d = data.defects[0]
    assert (d.key, d.status, d.severity, d.category) == ("77", Status.CLOSED, Severity.S3, Category.DATA)
    assert d.closed is not None


def test_auth_error_is_clear():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    conn = JiraConnector({"base_url": "https://x.atlassian.net"}, Mapping(), client)
    try:
        conn.fetch()
    except Exception as exc:  # noqa: BLE001
        assert "401" in str(exc)
    else:
        raise AssertionError("expected an error")
