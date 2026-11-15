"""Fintech Test Quality Report: API.

Run:  ./run.sh  (Windows: run.bat), from the backend folder
Docs: http://localhost:8800/docs

Configuration (env vars):
    FTQ_SOURCES  path to sources.yaml (which tools to read). Default: demo data.
    FTQ_MAPPING  path to mapping.yaml (field and value mapping).
"""
from __future__ import annotations

import inspect
import os
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException

from .connectors import REGISTRY, ConnectorError
from .mapping import Mapping
from .model import Dataset
from .reports import REPORTS

class Store:
    """In-memory store. Swap for Postgres when multi-client hosting starts."""

    def __init__(self) -> None:
        self.data = Dataset()
        self.synced_at: datetime | None = None
        self.errors: list[str] = []


STORE = Store()


def load_sources() -> list[dict[str, Any]]:
    path = os.environ.get("FTQ_SOURCES")
    if path and Path(path).exists():
        return (yaml.safe_load(Path(path).read_text()) or {}).get("sources", [])
    return [{"type": "demo"}]


def load_mapping() -> Mapping:
    return Mapping.load(os.environ.get("FTQ_MAPPING"))


def sync() -> dict[str, Any]:
    mapping = load_mapping()
    data, errors, counts = Dataset(), [], {}
    for src in load_sources():
        kind = src.get("type")
        cls = REGISTRY.get(kind)
        if cls is None:
            errors.append(f"Unknown source type: {kind}")
            continue
        try:
            part = cls(src.get("settings", {}), mapping).fetch()
        except (ConnectorError, KeyError, OSError) as exc:
            errors.append(f"{kind}: {exc}")
            continue
        data.extend(part)
        counts[src.get("name", kind)] = {"defects": len(part.defects), "runs": len(part.runs)}
    STORE.data, STORE.errors, STORE.synced_at = data, errors, datetime.now()
    return {"synced_at": STORE.synced_at, "sources": counts, "errors": errors}


@asynccontextmanager
async def lifespan(_: FastAPI):
    sync()
    yield


app = FastAPI(title="Fintech Test Quality Report", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "synced_at": STORE.synced_at,
            "defects": len(STORE.data.defects), "runs": len(STORE.data.runs), "errors": STORE.errors}


@app.get("/connectors")
def connectors() -> list[str]:
    return sorted(REGISTRY)


@app.post("/sync")
def post_sync() -> dict[str, Any]:
    return sync()


@app.get("/reports")
def list_reports() -> list[str]:
    return sorted(REPORTS)


@app.get("/reports/{name}")
def report(name: str, as_of: datetime | None = None) -> Any:
    fn = REPORTS.get(name)
    if fn is None:
        raise HTTPException(404, f"Unknown report '{name}'. See /reports.")
    if "as_of" in inspect.signature(fn).parameters:
        return fn(STORE.data, as_of=as_of)
    return fn(STORE.data)


@app.get("/mapping/gaps")
def mapping_gaps() -> dict[str, dict[str, int]]:
    """Tool values the mapping did not recognise, with counts: the to-do list for the mapping screen."""
    gaps: dict[str, Counter] = {}
    for d in STORE.data.defects:
        for field, value in d.raw_unmapped.items():
            gaps.setdefault(f"{d.tool}.{field}", Counter())[value] += 1
    return {k: dict(v.most_common()) for k, v in gaps.items()}
