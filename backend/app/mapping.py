"""Field and value mapping.

Each tool names things differently ("Blocker" vs "1-Critical", "Closed" vs
"Verified"). A client maps their values once, in a YAML file; after that every
report works the same. Built-in defaults cover the common names, so a new
client gets useful reports before any mapping is done. Values that cannot be
mapped are kept in `Defect.raw_unmapped` and listed by `/mapping/gaps`, so the
mapping screen can show exactly what still needs a decision.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .masking import mask_text
from .model import (Category, Channel, Defect, Interface, Priority, Severity,
                    Source, Status, TestLevel)

# Logical fields a connector can fill, and the enum each one maps to.
ENUM_FIELDS: dict[str, type] = {
    "severity": Severity,
    "priority": Priority,
    "status": Status,
    "category": Category,
    "found_in": TestLevel,
    "source": Source,
    "channel": Channel,
    "interface": Interface,
}

DEFAULT_VALUES: dict[str, dict[str, str]] = {
    "severity": {
        "blocker": "S1", "critical": "S1", "1-critical": "S1", "sev1": "S1", "s1": "S1", "urgent": "S1",
        "major": "S2", "high": "S2", "2-high": "S2", "sev2": "S2", "s2": "S2",
        "medium": "S3", "normal": "S3", "3-medium": "S3", "sev3": "S3", "s3": "S3", "average": "S3",
        "minor": "S4", "low": "S4", "trivial": "S4", "cosmetic": "S4", "4-low": "S4", "5-low": "S4",
        "sev4": "S4", "s4": "S4",
    },
    "priority": {
        "highest": "P1", "urgent": "P1", "p1": "P1", "1-immediate": "P1", "immediate": "P1",
        "high": "P2", "p2": "P2", "2-high": "P2",
        "medium": "P3", "p3": "P3", "3-medium": "P3", "normal": "P3",
        "low": "P4", "lowest": "P4", "p4": "P4", "4-low": "P4", "5-low": "P4",
    },
    "status": {
        "new": "New", "to do": "New", "open": "New", "submitted": "New", "backlog": "New",
        "assigned": "Assigned", "triaged": "Assigned", "accepted": "Assigned",
        "in progress": "Open", "in development": "Open", "working": "Open",
        "fixed": "Fixed", "resolved": "Fixed", "ready for test": "Fixed", "in review": "Fixed",
        "retest": "Retest", "in test": "Retest", "in qa": "Retest",
        "reopen": "Reopened", "reopened": "Reopened",
        "verified": "Verified",
        "closed": "Closed", "done": "Closed",
        "rejected": "Rejected", "duplicate": "Rejected", "won't fix": "Rejected",
        "not a bug": "Rejected", "works as designed": "Rejected", "cannot reproduce": "Rejected",
        "deferred": "Deferred", "postponed": "Deferred", "later release": "Deferred",
    },
    "category": {c.value.lower(): c.value for c in Category} | {
        "functionality": "Functional", "test data": "Data", "env": "Environment",
        "integration": "Interface", "ui": "Usability", "browser": "Compatibility",
        "perf": "Performance", "a11y": "Accessibility", "cannot reproduce": "Not reproducible",
    },
    "found_in": {
        "unit": "Unit", "system": "System", "sit": "SIT", "system integration": "SIT",
        "e2e": "E2E", "end to end": "E2E", "end-to-end": "E2E", "uat": "UAT",
        "penny": "Penny", "penny test": "Penny", "production": "Production", "prod": "Production",
    },
    "source": {s.value.lower(): s.value for s in Source} | {
        "automated": "Automation", "regression suite": "Automation", "load test": "Performance",
        "pen test": "Security", "dast": "Security", "sast": "Security", "audit": "Compliance",
        "incident": "Production",
    },
    "channel": {
        "mobile": "Mobile app", "ios": "Mobile app", "android": "Mobile app", "mobile app": "Mobile app",
        "web": "Web", "browser": "Web", "api": "APIs and backend", "backend": "APIs and backend",
        "apis and backend": "APIs and backend", "batch": "APIs and backend",
        "legacy": "Legacy", "mainframe": "Legacy",
    },
    "interface": {i.value.lower(): i.value for i in Interface},
}


class Mapping:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @classmethod
    def load(cls, path: str | Path | None) -> "Mapping":
        if not path or not Path(path).exists():
            return cls({})
        return cls(yaml.safe_load(Path(path).read_text()) or {})

    # --- config lookups -------------------------------------------------
    def tool_config(self, tool: str) -> dict[str, Any]:
        return (self.config.get("tools") or {}).get(tool) or {}

    def field_name(self, tool: str, logical: str, default: str | None = None) -> str | None:
        """Which tool field holds a logical field (e.g. severity -> customfield_10050)."""
        return (self.tool_config(tool).get("fields") or {}).get(logical, default)

    def _value_map(self, tool: str, logical: str) -> dict[str, str]:
        custom = (self.tool_config(tool).get("values") or {}).get(logical) or {}
        merged = dict(DEFAULT_VALUES.get(logical, {}))
        merged.update({str(k).strip().lower(): str(v) for k, v in custom.items()})
        return merged

    # --- mapping ----------------------------------------------------------
    def map_value(self, tool: str, logical: str, raw: Any) -> tuple[Any, bool]:
        """Return (enum value or None, recognised?)."""
        if raw is None or str(raw).strip() == "":
            return None, True
        enum = ENUM_FIELDS[logical]
        target = self._value_map(tool, logical).get(str(raw).strip().lower())
        if target is None:
            return None, False
        return enum(target), True

    def to_defect(self, tool: str, key: str, raw: dict[str, Any]) -> Defect:
        """Build a Defect from logical-field raw values a connector extracted."""
        values: dict[str, Any] = {}
        unmapped: dict[str, str] = {}
        for logical in ENUM_FIELDS:
            mapped, ok = self.map_value(tool, logical, raw.get(logical))
            if mapped is not None:
                values[logical] = mapped
            elif not ok:
                unmapped[logical] = str(raw.get(logical))

        text ={k: mask_text(str(raw.get(k) or "")) for k in (
            "title", "application", "owner_team", "epic", "feature", "story", "sprint")}

        return Defect(
            id=f"{tool}:{key}", tool=tool, key=key,
            created=_parse_dt(raw.get("created")) or datetime.min,
            closed=_parse_dt(raw.get("closed")),
            reopen_count=int(raw.get("reopen_count") or 0),
            exploratory="explor" in str(raw.get("test_type") or "").lower(),
            raw_unmapped=unmapped,
            **text, **values,
        )


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).strip().replace("Z", "+00:00")
    # Jira sends +0000 without a colon
    if len(s) > 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return None
