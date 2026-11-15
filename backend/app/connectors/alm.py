"""OpenText ALM / Quality Center connector (read only).

Uses the ALM REST API under /qcbin. Sign-in with an API key
(POST /qcbin/rest/oauth2/login) or, for older servers, basic auth
(GET /qcbin/api/authentication/sign-in). The session cookies are then sent on
every call.

Settings:
    base_url:      https://alm.yourcompany.com/qcbin
    domain:        PAYMENTS
    project:       WIRES
    client_id:     ${ALM_CLIENT_ID}       # API key (preferred)
    client_secret: ${ALM_CLIENT_SECRET}
    # or username / password for basic sign-in

ALM entities come back as {"Fields": [{"Name": ..., "values": [{"value": ...}]}]}.
Custom fields are named user-01, user-02, ...; map them in tools.alm.fields.
"""
from __future__ import annotations

from typing import Any

from ..model import Dataset, TestRun
from .base import Connector

DEFAULT_FIELDS = {
    "title": "name",
    "status": "status",
    "severity": "severity",
    "priority": "priority",
    "category": None,
    "found_in": None,
    "source": None,
    "channel": None,
    "interface": None,
    "application": None,
    "owner_team": None,
    "test_type": None,
    "epic": None,
    "feature": None,
    "story": None,
    "sprint": "detected-in-rel",
    "created": "creation-time",
    "closed": "closing-date",
    "reopen_count": None,
}


def _fields(entity: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in entity.get("Fields") or []:
        vals = f.get("values") or []
        out[f.get("Name")] = vals[0].get("value") if vals else None
    return out


class AlmConnector(Connector):
    tool = "alm"

    def _sign_in(self) -> None:
        base = self.settings["base_url"].rstrip("/")
        if self.settings.get("client_id"):
            r = self.client.post(f"{base}/rest/oauth2/login",
                                 json={"clientId": self.settings["client_id"],
                                       "secret": self.settings.get("client_secret", "")})
        else:
            r = self.client.get(f"{base}/api/authentication/sign-in",
                                auth=(self.settings.get("username", ""), self.settings.get("password", "")))
        self._check(r)

    def _entities(self, collection: str) -> list[dict[str, Any]]:
        base = self.settings["base_url"].rstrip("/")
        url = f"{base}/rest/domains/{self.settings['domain']}/projects/{self.settings['project']}/{collection}"
        out: list[dict[str, Any]] = []
        start = 1
        for _ in range(self.max_pages):
            r = self._check(self.client.get(url, params={"page-size": self.page_size, "start-index": start},
                                            headers={"Accept": "application/json"}))
            body = r.json()
            batch = body.get("entities", [])
            out.extend(_fields(e) for e in batch)
            start += len(batch)
            if not batch or start > int(body.get("TotalResults", 0)):
                break
        return out

    def fetch(self) -> Dataset:
        self._sign_in()
        fmap = {k: self.field(k, v) for k, v in DEFAULT_FIELDS.items()}
        data = Dataset()
        for f in self._entities("defects"):
            raw = {logical: f.get(name) for logical, name in fmap.items() if name}
            data.defects.append(self.mapping.to_defect(self.tool, str(f.get("id")), raw))

        if self.settings.get("include_runs", True):
            for f in self._entities("runs"):
                data.runs.append(TestRun(id=f"alm:{f.get('id')}", tool=self.tool, key=str(f.get("id")),
                                         status=str(f.get("status") or "Not run")))
        return data
