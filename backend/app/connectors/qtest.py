"""Tricentis qTest Manager connector (read only).

Uses the v3 search API: POST /api/v3/projects/{projectId}/search with
object_type "defects" and "test-runs". Auth: bearer API token.

Settings:
    base_url:   https://yourcompany.qtestnet.com
    token:      ${QTEST_TOKEN}
    project_id: 12345
    defect_query: "'Status' <> 'Closed'"   # optional; default = all

qTest returns each value as a property: {field_name, field_value, field_value_name}.
Field names below are qTest's default labels; site admins often rename them,
so override them in tools.qtest.fields in the mapping file.
"""
from __future__ import annotations

from typing import Any

from ..model import Dataset, TestRun
from .base import Connector

DEFAULT_FIELDS = {
    "title": "Summary",
    "status": "Status",
    "severity": "Severity",
    "priority": "Priority",
    "category": "Type",
    "found_in": "Test Level",
    "source": "Defect Source",
    "channel": "Channel",
    "interface": "Interface",
    "application": "Module",
    "owner_team": "Assigned Team",
    "test_type": "Test Type",
    "epic": "Epic",
    "feature": "Feature",
    "story": "Story",
    "sprint": "Target Release/Build",
    "created": "created_date",
    "closed": "Closed Date",
}

RUN_FIELDS = {"status": "Status", "level": "Test Level", "story": "Story", "planned": "Run Type"}


def _props(item: dict[str, Any]) -> dict[str, Any]:
    out = {p.get("field_name"): (p.get("field_value_name") or p.get("field_value"))
           for p in item.get("properties") or []}
    # top-level values (dates, ids, name) as fall-backs
    for k in ("created_date", "last_modified_date", "name", "pid"):
        if k in item and k not in out:
            out[k] = item[k]
    return out


class QTestConnector(Connector):
    tool = "qtest"

    def _search(self, object_type: str, query: str) -> list[dict[str, Any]]:
        base = self.settings["base_url"].rstrip("/")
        pid = self.settings["project_id"]
        headers = {"Authorization": f"Bearer {self.settings.get('token', '')}",
                   "Content-Type": "application/json"}
        items: list[dict[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            r = self._check(self.client.post(
                f"{base}/api/v3/projects/{pid}/search",
                params={"page": page, "pageSize": self.page_size},
                json={"object_type": object_type, "fields": ["*"], "query": query},
                headers=headers))
            batch = r.json().get("items", [])
            items.extend(batch)
            if len(batch) < self.page_size:
                break
        return items

    def fetch(self) -> Dataset:
        fmap = {k: self.field(k, v) for k, v in DEFAULT_FIELDS.items()}
        data = Dataset()
        for item in self._search("defects", self.settings.get("defect_query", "'Id' > 0")):
            props = _props(item)
            raw = {logical: props.get(name) for logical, name in fmap.items() if name}
            key = str(item.get("pid") or item.get("id"))
            data.defects.append(self.mapping.to_defect(self.tool, key, raw))

        if self.settings.get("include_runs", True):
            rmap = {k: self.mapping.field_name("qtest_runs", k, v) for k, v in RUN_FIELDS.items()}
            for item in self._search("test-runs", self.settings.get("run_query", "'Id' > 0")):
                props = _props(item)
                level, _ = self.mapping.map_value(self.tool, "found_in", props.get(rmap["level"]))
                run_type = str(props.get(rmap["planned"]) or "").lower()
                data.runs.append(TestRun(
                    id=f"qtest:{item.get('pid') or item.get('id')}", tool=self.tool,
                    key=str(item.get("pid") or item.get("id")),
                    status=str(props.get(rmap["status"]) or "Not run"),
                    level=level or "Unknown", planned="exploratory" not in run_type,
                    story=str(props.get(rmap["story"]) or ""),
                ))
        return data
