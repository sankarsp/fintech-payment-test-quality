"""Jira Cloud connector (read only).

Uses the enhanced search endpoint GET /rest/api/3/search/jql, which pages with
`nextPageToken`. Auth: Atlassian account email + API token (basic auth).

Settings:
    base_url:  https://your-site.atlassian.net
    email:     ${JIRA_EMAIL}
    api_token: ${JIRA_API_TOKEN}
    jql:       project = PAY AND issuetype = Bug

Field names come from the mapping file (tools.jira.fields). Two shortcuts are
supported for teams that keep values in labels or components:
    category: "label:cat-"      -> label "cat-data" gives category "data"
    channel:  "component"       -> first component name
"""
from __future__ import annotations

from typing import Any

from ..model import Dataset
from .base import Connector

DEFAULT_FIELDS = {
    "title": "summary",
    "status": "status",
    "priority": "priority",
    "severity": None,       # usually a custom field, e.g. customfield_10050
    "category": None,
    "found_in": None,
    "source": None,
    "channel": None,
    "interface": None,
    "application": None,
    "owner_team": None,
    "test_type": None,
    "epic": "parent",
    "feature": None,
    "story": None,
    "sprint": None,         # e.g. customfield_10020
    "created": "created",
    "closed": "resolutiondate",
}


def _plain(value: Any) -> Any:
    """Jira returns objects ({name}, {value}, {key}), lists or plain strings."""
    if value is None:
        return None
    if isinstance(value, list):
        return _plain(value[-1]) if value else None  # sprints: the latest one
    if isinstance(value, dict):
        for k in ("value", "name", "key", "displayName"):
            if k in value:
                return value[k]
    return value


class JiraConnector(Connector):
    tool = "jira"

    def _field_map(self) -> dict[str, str | None]:
        return {k: self.field(k, v) for k, v in DEFAULT_FIELDS.items()}

    def _extract(self, issue: dict[str, Any], fmap: dict[str, str | None]) -> dict[str, Any]:
        fields = issue.get("fields") or {}
        raw: dict[str, Any] = {}
        for logical, name in fmap.items():
            if not name:
                continue
            if name.startswith("label:"):
                prefix = name[len("label:"):].lower()
                hit = next((l for l in fields.get("labels") or [] if l.lower().startswith(prefix)), None)
                raw[logical] = hit[len(prefix):] if hit else None
            elif name == "component":
                comps = fields.get("components") or []
                raw[logical] = comps[0].get("name") if comps else None
            else:
                raw[logical] = _plain(fields.get(name))
        return raw

    def fetch(self) -> Dataset:
        base = self.settings["base_url"].rstrip("/")
        auth = (self.settings.get("email", ""), self.settings.get("api_token", ""))
        fmap = self._field_map()
        wanted = sorted({n for n in fmap.values()
                         if n and not n.startswith("label:") and n != "component"} | {"labels", "components"})
        params: dict[str, Any] = {
            "jql": self.settings.get("jql", "issuetype = Bug ORDER BY created ASC"),
            "fields": ",".join(wanted),
            "maxResults": self.page_size,
        }
        data = Dataset()
        for _ in range(self.max_pages):
            r = self._check(self.client.get(f"{base}/rest/api/3/search/jql", params=params,
                                            auth=auth, headers={"Accept": "application/json"}))
            body = r.json()
            for issue in body.get("issues", []):
                data.defects.append(self.mapping.to_defect(self.tool, issue["key"], self._extract(issue, fmap)))
            token = body.get("nextPageToken")
            if body.get("isLast", token is None) or not token:
                break
            params["nextPageToken"] = token
        return data
