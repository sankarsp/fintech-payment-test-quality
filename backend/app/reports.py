"""The reports every test lead should share.

Each function reads only the common model, so it works for any tool.
Definitions follow the article "Sell me this defect":
  * Leakage after a level = bugs found after that level / all bugs x 100
  * Reopen rate = bugs reopened at least once / bugs fixed x 100
  * Defect age = days a bug has been open
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from .model import (LEVEL_ORDER, Category, Dataset, Defect, Interface, Severity,
                    Source, Status, TestLevel)

FIXED_STATES = {Status.FIXED, Status.RETEST, Status.VERIFIED, Status.CLOSED, Status.REOPENED}


def _open(d: Dataset) -> list[Defect]:
    return [x for x in d.defects if x.status.is_open]


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _as_of(d: Dataset, as_of: datetime | None) -> datetime:
    if as_of:
        return as_of
    stamps = [x.created for x in d.defects] + [x.closed for x in d.defects if x.closed]
    return max(stamps) if stamps else datetime.now()


# --- single numbers ---------------------------------------------------------
def leakage(d: Dataset) -> dict[str, Any]:
    total = len(d.defects)
    by_level = Counter(x.found_in for x in d.defects)
    rows = []
    for i, level in enumerate(LEVEL_ORDER[:-1]):
        later = sum(by_level[l] for l in LEVEL_ORDER[i + 1:])
        rows.append({"after": level.value, "bugs_found_later": later, "leakage_pct": _pct(later, total)})
    prod = by_level[TestLevel.PRODUCTION]
    return {"total_bugs": total, "production_bugs": prod,
            "production_leakage_pct": _pct(prod, total), "by_level": rows}


def reopen_rate(d: Dataset) -> float:
    fixed = [x for x in d.defects if x.status in FIXED_STATES or x.reopen_count]
    return _pct(sum(1 for x in fixed if x.reopen_count), len(fixed))


def defect_age(d: Dataset, as_of: datetime | None = None) -> dict[str, Any]:
    now = _as_of(d, as_of)
    buckets = {"0-7 days": 0, "8-14 days": 0, "15-30 days": 0, "31+ days": 0}
    oldest: Defect | None = None
    for x in _open(d):
        age = (now - x.created).days
        key = "0-7 days" if age <= 7 else "8-14 days" if age <= 14 else "15-30 days" if age <= 30 else "31+ days"
        buckets[key] += 1
        if oldest is None or x.created < oldest.created:
            oldest = x
    return {"buckets": buckets,
            "oldest": None if oldest is None else {
                "key": oldest.key, "days": (now - oldest.created).days,
                "owner_team": oldest.owner_team, "severity": oldest.severity.value}}


# --- breakdowns ---------------------------------------------------------------
def breakdown(d: Dataset, field: str, include_all: list[str] | None = None,
              skip: set[str] | None = None) -> list[dict[str, Any]]:
    counts = Counter(getattr(x, field).value if hasattr(getattr(x, field), "value") else getattr(x, field)
                     for x in d.defects)
    keys = include_all or [k for k, _ in counts.most_common()]
    rows = [{"name": k, "bugs": counts.get(k, 0)} for k in keys if k not in (skip or set())]
    return sorted(rows, key=lambda r: -r["bugs"])


def by_category(d: Dataset):
    return breakdown(d, "category", [c.value for c in Category if c != Category.UNKNOWN])


def by_source(d: Dataset):
    return breakdown(d, "source", [s.value for s in Source if s != Source.UNKNOWN])


def by_interface(d: Dataset):
    return breakdown(d, "interface", [i.value for i in Interface], skip={"None"})


def by_channel(d: Dataset):
    return breakdown(d, "channel")


def application_by_priority(d: Dataset) -> list[dict[str, Any]]:
    table: dict[str, Counter] = defaultdict(Counter)
    for x in d.defects:
        group = "P1-P2" if x.priority.value in ("P1", "P2") else "P3-P4"
        table[x.application or "Unknown"][group] += 1
    rows = [{"application": app, "P1-P2": c["P1-P2"], "P3-P4": c["P3-P4"]} for app, c in table.items()]
    rows.sort(key=lambda r: -(r["P1-P2"] + r["P3-P4"]))
    rows.append({"application": "Total", "P1-P2": sum(r["P1-P2"] for r in rows),
                 "P3-P4": sum(r["P3-P4"] for r in rows)})
    return rows


def planned_vs_exploratory(d: Dataset) -> dict[str, int]:
    explo = sum(1 for x in d.defects if x.exploratory)
    return {"planned": len(d.defects) - explo, "exploratory": explo}


def by_sprint(d: Dataset) -> list[dict[str, Any]]:
    counts = Counter(x.sprint or "No sprint" for x in d.defects)
    return [{"sprint": k, "bugs": v} for k, v in sorted(counts.items())]


def weekly_trend(d: Dataset, weeks: int = 8, as_of: datetime | None = None) -> list[dict[str, Any]]:
    now = _as_of(d, as_of)
    start = now - timedelta(weeks=weeks)
    rows = []
    for w in range(weeks):
        lo, hi = start + timedelta(weeks=w), start + timedelta(weeks=w + 1)
        opened = sum(1 for x in d.defects if lo < x.created <= hi)
        closed = sum(1 for x in d.defects if x.closed and lo < x.closed <= hi)
        still_open = sum(1 for x in d.defects if x.created <= hi and (x.closed is None or x.closed > hi))
        rows.append({"week": w + 1, "opened": opened, "closed": closed, "open_at_end": still_open})
    return rows


# --- epic / feature / story readiness -------------------------------------
def readiness(d: Dataset) -> dict[str, Any]:
    stories: dict[str, dict[str, Any]] = {}
    for r in d.runs:
        if not r.story:
            continue
        s = stories.setdefault(r.story, {"feature": r.feature, "epic": r.epic, "runs": 0, "not_run": 0})
        s["runs"] += 1
        s["not_run"] += r.status.lower() in ("not run", "unexecuted", "no run", "blocked")
    blockers = {x.feature for x in _open(d) if x.severity in (Severity.S1, Severity.S2) and x.feature}
    features: dict[str, dict[str, Any]] = {}
    for name, s in stories.items():
        f = features.setdefault(s["feature"], {"epic": s["epic"], "stories": 0, "tested": 0})
        f["stories"] += 1
        f["tested"] += s["not_run"] == 0
    for name, f in features.items():
        f["ready"] = f["tested"] == f["stories"] and name not in blockers
    epics: dict[str, dict[str, Any]] = {}
    for name, f in features.items():
        e = epics.setdefault(f["epic"], {"features": 0, "ready": 0})
        e["features"] += 1
        e["ready"] += f["ready"]
    for e in epics.values():
        e["on_track"] = e["ready"] == e["features"]
    return {
        "stories_tested": sum(s["not_run"] == 0 for s in stories.values()),
        "stories_total": len(stories),
        "features_ready": sum(f["ready"] for f in features.values()),
        "features_total": len(features),
        "epics_on_track": sum(e["on_track"] for e in epics.values()),
        "epics_total": len(epics),
        "not_ready_features": sorted(n for n, f in features.items() if not f["ready"]),
        "at_risk_epics": sorted(n for n, e in epics.items() if not e["on_track"]),
    }


# --- the weekly summary and go / no-go ----------------------------------------
def test_execution(d: Dataset) -> dict[str, int]:
    planned = [r for r in d.runs if r.planned]
    run = [r for r in planned if r.status.lower() not in ("not run", "unexecuted", "no run")]
    passed = [r for r in run if r.status.lower() in ("passed", "pass")]
    return {"planned": len(planned), "run": len(run), "passed": len(passed)}


def weekly_summary(d: Dataset, as_of: datetime | None = None) -> dict[str, Any]:
    open_bugs = _open(d)
    return {
        "tests": test_execution(d),
        "open_bugs": len(open_bugs),
        "open_critical": sum(x.severity == Severity.S1 for x in open_bugs),
        "open_high": sum(x.severity == Severity.S2 for x in open_bugs),
        "leakage_pct": leakage(d)["production_leakage_pct"],
        "reopen_pct": reopen_rate(d),
        "oldest_open": defect_age(d, as_of)["oldest"],
        "readiness": readiness(d),
    }


DEFAULT_GATES = {
    # hard gates: any miss means No-go
    "max_open_critical": 0,
    "min_pass_rate_pct": 90.0,
    "min_stories_tested_pct": 80.0,
    # soft gates: a miss means Go with conditions
    "max_open_high": 3,
    "max_leakage_pct": 5.0,
    "max_reopen_pct": 10.0,
    "target_pass_rate_pct": 95.0,
}


def go_no_go(d: Dataset, gates: dict[str, float] | None = None,
             as_of: datetime | None = None) -> dict[str, Any]:
    g = {**DEFAULT_GATES, **(gates or {})}
    s = weekly_summary(d, as_of)
    t = s["tests"]
    pass_rate = _pct(t["passed"], t["run"])
    stories_pct = _pct(s["readiness"]["stories_tested"], s["readiness"]["stories_total"])
    checks = [
        ("Open critical bugs", s["open_critical"], f"<= {g['max_open_critical']}", s["open_critical"] <= g["max_open_critical"], "hard"),
        ("Pass rate %", pass_rate, f">= {g['min_pass_rate_pct']}", pass_rate >= g["min_pass_rate_pct"], "hard"),
        ("Stories tested %", stories_pct, f">= {g['min_stories_tested_pct']}", stories_pct >= g["min_stories_tested_pct"], "hard"),
        ("Open high bugs", s["open_high"], f"<= {g['max_open_high']}", s["open_high"] <= g["max_open_high"], "soft"),
        ("Production leakage %", s["leakage_pct"], f"<= {g['max_leakage_pct']}", s["leakage_pct"] <= g["max_leakage_pct"], "soft"),
        ("Reopen rate %", s["reopen_pct"], f"<= {g['max_reopen_pct']}", s["reopen_pct"] <= g["max_reopen_pct"], "soft"),
        ("Pass rate target %", pass_rate, f">= {g['target_pass_rate_pct']}", pass_rate >= g["target_pass_rate_pct"], "soft"),
    ]
    rows = [{"kpi": k, "actual": a, "target": tgt, "met": met, "gate": gate} for k, a, tgt, met, gate in checks]
    if any(not r["met"] and r["gate"] == "hard" for r in rows):
        decision = "No-go"
    elif any(not r["met"] for r in rows):
        decision = "Go with conditions"
    else:
        decision = "Go"
    return {"decision": decision, "kpis": rows,
            "not_ready": s["readiness"]["not_ready_features"],
            "note": "The tool recommends; the release owner decides."}


REPORTS = {
    "weekly-summary": weekly_summary,
    "trend": weekly_trend,
    "leakage": leakage,
    "age": defect_age,
    "sprint": by_sprint,
    "category": by_category,
    "source": by_source,
    "interface": by_interface,
    "channel": by_channel,
    "application-priority": application_by_priority,
    "planned-vs-exploratory": planned_vs_exploratory,
    "readiness": readiness,
    "go-no-go": go_no_go,
}
