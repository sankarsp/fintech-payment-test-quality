"""Base class for all connectors.

A connector only READS from the tool. It turns the tool's records into the
common model (Defect, TestRun) using the client's Mapping.
"""
from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..mapping import Mapping
from ..model import Dataset

_ENV = re.compile(r"\$\{([A-Z0-9_]+)\}")


def expand_env(value: Any) -> Any:
    """Allow secrets in config as ${JIRA_API_TOKEN}, never as plain text."""
    if isinstance(value, str):
        return _ENV.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    return value


class ConnectorError(RuntimeError):
    pass


class Connector(ABC):
    tool: str = ""
    page_size: int = 100
    max_pages: int = 500  # safety stop

    def __init__(self, settings: dict[str, Any], mapping: Mapping,
                 client: httpx.Client | None = None):
        self.settings = expand_env(settings or {})
        self.mapping = mapping
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0, follow_redirects=True)
        return self._client

    def field(self, logical: str, default: str | None = None) -> str | None:
        return self.mapping.field_name(self.tool, logical, default)

    def _check(self, response: httpx.Response) -> httpx.Response:
        if response.status_code == 401:
            raise ConnectorError(f"{self.tool}: sign-in failed (401). Check the API token.")
        if response.status_code == 403:
            raise ConnectorError(f"{self.tool}: no permission (403) for {response.request.url.path}.")
        if response.status_code >= 400:
            raise ConnectorError(f"{self.tool}: HTTP {response.status_code} on {response.request.url.path}")
        return response

    @abstractmethod
    def fetch(self) -> Dataset:
        """Read defects (and test runs, where the tool has them)."""

    def test_connection(self) -> bool:
        """Cheap call used by the setup screen."""
        self.fetch()
        return True
