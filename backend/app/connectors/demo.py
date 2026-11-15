"""Demo connector: realistic sample data, no tool needed.

The numbers match the sample reports in the article "Sell me this defect"
(paymentconsultant.top/sell-me-this-defect/): 198 bugs, 50 open (2 critical,
6 high), 3% production leakage, 412 of 450 tests run, 389 passed, week 8.
The data is generated, not taken from any client.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from ..model import Dataset, TestRun
from .base import Connector

AS_OF = datetime(2026, 11, 13, 17, 0)   # Friday of week 8
START = AS_OF - timedelta(weeks=8)

CATEGORIES = [("Functional", 58), ("Data", 30), ("Environment", 24), ("Requirement", 22),
              ("Interface", 15), ("Usability", 14), ("Compatibility", 10), ("Performance", 9),
              ("Security", 6), ("Accessibility", 5), ("Not reproducible", 3), ("Tester error", 2)]
SOURCES = [("Manual", 90), ("Automation", 68), ("Performance", 14), ("Compliance", 11),
           ("Security", 9), ("Production", 6)]
# channel: (total bugs, how many are P1-P2)
CHANNELS = [("Mobile app", 64, 9), ("APIs and backend", 57, 8), ("Web", 51, 5), ("Legacy", 26, 3)]
INTERFACES = [("Downstream", 5), ("Upstream", 4), ("External", 4), ("Legacy", 2)]

# epic -> feature -> number of stories (40 in total)
PLAN = {
    "Domestic wires": {"Wire initiation": 6, "Wire approvals": 3, "Scheduled wires": 3},
    "Scheduled payments": {"Recurring setup": 7, "Payment reminders": 6},
    "Payee management": {"Add payee": 8, "Payee verification": 7},
}
NOT_READY = {"Wire approvals", "Scheduled wires"}
LEVELS = ["Unit", "System", "SIT", "E2E", "UAT", "Penny"]
TEAMS = ["Payments team", "Mobile team", "Web team", "Core banking team", "Fraud team"]


def _expand(pairs):
    out = []
    for value, n in pairs:
        out += [value] * n
    return out


def _stories():
    out = []
    n = 0
    for epic, feats in PLAN.items():
        for feat, count in feats.items():
            for _ in range(count):
                n += 1
                out.append((epic, feat, f"PAY-{100 + n}"))
    return out


def build(rng: random.Random | None = None) -> tuple[list[dict], list[TestRun]]:
    rng = rng or random.Random(8)
    total = 198
    categories = _expand(CATEGORIES)
    sources = _expand(SOURCES)
    rng.shuffle(sources)
    channels, high_prio = [], []
    for name, n, hi in CHANNELS:
        channels += [name] * n
        high_prio += [True] * hi + [False] * (n - hi)
    order = list(range(total))
    rng.shuffle(order)
    channels = [channels[i] for i in order]
    high_prio = [high_prio[i] for i in order]
    interfaces = iter(_expand(INTERFACES))
    stories = _stories()
    not_ready_stories = [s for s in stories if s[1] in NOT_READY]

    # pick the 50 open bugs among non-production ones; 2 critical + 6 high go to not-ready features
    candidates = [i for i in range(total) if sources[i] != "Production"]
    open_ids = set(rng.sample(candidates, 50))
    urgent = sorted(i for i in open_ids if high_prio[i])
    s1_open, s2_open = set(urgent[:2]), set(urgent[2:8])

    raws = []
    for i in range(total):
        is_open = i in open_ids
        if i in s1_open:
            sev = "Critical"
        elif i in s2_open:
            sev = "High"
        elif is_open:
            sev = rng.choice(["Medium", "Medium", "Low"])
        else:
            sev = rng.choice(["Critical", "High", "High", "Medium", "Medium", "Medium", "Low"])
        prio = ("Highest" if sev == "Critical" else "High") if high_prio[i] else rng.choice(["Medium", "Low"])
        epic, feat, story = rng.choice(not_ready_stories if (i in s1_open or i in s2_open) else stories)
        created = START + timedelta(hours=rng.randint(0, 8 * 7 * 24 - 48))
        if is_open:  # open bugs are all younger than the oldest one (41 days)
            created = max(created, AS_OF - timedelta(days=40))
        status, closed = "New", None
        if is_open:
            status = rng.choice(["New", "Assigned", "In Progress", "Ready for test", "Retest", "Deferred"])
        else:
            closed = min(created + timedelta(days=rng.randint(1, 12)), AS_OF)
            status = rng.choice(["Closed"] * 9 + ["Rejected"])
        cat = categories[i]
        raws.append({
            "key": f"BUG-{1001 + i}",
            "title": f"{feat}: {cat.lower()} issue #{i + 1}",
            "severity": sev, "priority": prio, "status": status, "category": cat,
            "source": sources[i],
            "found_in": "Production" if sources[i] == "Production" else rng.choice(LEVELS),
            "channel": channels[i], "application": channels[i],
            "interface": next(interfaces) if cat == "Interface" else "None",
            "owner_team": rng.choice(TEAMS), "epic": epic, "feature": feat, "story": story,
            "sprint": f"Sprint {min(4, (created - START).days // 14 + 1)}",
            "created": created.isoformat(), "closed": closed.isoformat() if closed else None,
            "reopen_count": 0, "test_type": "planned",
        })

    # 58 bugs found in exploratory sessions
    for r in rng.sample(raws, 58):
        r["test_type"] = "exploratory"
    # 10 of the fixed bugs were reopened once (about 6% reopen rate)
    fixed = [r for r in raws if r["status"] in ("Closed", "Ready for test", "Retest")]
    for r in rng.sample(fixed, 10):
        r["reopen_count"] = 1
    # the oldest open bug: 41 days, owned by the core banking team
    oldest = next(r for r in raws if r["status"] not in ("Closed", "Rejected")
                  and r["severity"] in ("Medium", "Low"))
    oldest["created"] = (AS_OF - timedelta(days=41)).isoformat()
    oldest["owner_team"] = "Core banking team"
    oldest["interface"] = "Legacy" if oldest["category"] == "Interface" else oldest["interface"]

    # 450 planned test runs: 412 run (389 passed, 23 failed), 38 not run
    runs: list[TestRun] = []
    ready = [s for s in stories if s[1] not in NOT_READY]
    statuses = ["Not run"] * 38 + ["Failed"] * 23 + ["Passed"] * 389
    for n, st in enumerate(statuses):
        if st == "Not run":
            epic, feat, story = not_ready_stories[n % len(not_ready_stories)]
        elif n < 38 + 23 and n % 3 == 0:
            epic, feat, story = not_ready_stories[n % len(not_ready_stories)]
        else:
            epic, feat, story = ready[n % len(ready)]
        runs.append(TestRun(
            id=f"demo-run:{n + 1}", tool="demo", key=f"TR-{n + 1}", status=st,
            level=LEVELS[n % len(LEVELS)], planned=True, story=story, feature=feat, epic=epic,
            executed=None if st == "Not run" else START + timedelta(hours=rng.randint(0, 8 * 7 * 24))))
    return raws, runs


class DemoConnector(Connector):
    tool = "demo"

    def fetch(self) -> Dataset:
        raws, runs = build(random.Random(int(self.settings.get("seed", 8))))
        data = Dataset(runs=runs)
        for raw in raws:
            data.defects.append(self.mapping.to_defect(self.tool, raw["key"], raw))
        return data
