"""CSV connector: for teams that export from any tool (or Excel) into a file.

Settings:
    path: ./exports/bugs.csv
    runs_path: ./exports/runs.csv   # optional

Column names come from tools.csv.fields in the mapping file; by default the
column is the logical name itself (severity, status, category, ...).
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..mapping import ENUM_FIELDS
from ..model import Dataset, TestRun
from .base import Connector

LOGICAL = list(ENUM_FIELDS) + ["title", "application", "owner_team", "epic", "feature",
                               "story", "sprint", "created", "closed", "reopen_count", "test_type"]


class CsvConnector(Connector):
    tool = "csv"

    def fetch(self) -> Dataset:
        data = Dataset()
        key_col = self.field("key", "key")
        with Path(self.settings["path"]).open(newline="", encoding="utf-8-sig") as fh:
            for i, row in enumerate(csv.DictReader(fh), start=1):
                raw = {l: row.get(self.field(l, l) or l) for l in LOGICAL}
                data.defects.append(self.mapping.to_defect(self.tool, row.get(key_col) or str(i), raw))

        runs_path = self.settings.get("runs_path")
        if runs_path:
            with Path(runs_path).open(newline="", encoding="utf-8-sig") as fh:
                for i, row in enumerate(csv.DictReader(fh), start=1):
                    level, _ = self.mapping.map_value(self.tool, "found_in", row.get("level"))
                    data.runs.append(TestRun(
                        id=f"csv-run:{row.get('key') or i}", tool=self.tool, key=row.get("key") or str(i),
                        status=row.get("status") or "Not run", level=level or "Unknown",
                        planned=(row.get("type") or "planned").lower() != "exploratory",
                        story=row.get("story") or "", feature=row.get("feature") or "",
                        epic=row.get("epic") or ""))
        return data
