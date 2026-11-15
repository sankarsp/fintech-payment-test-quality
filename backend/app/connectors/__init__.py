from .alm import AlmConnector
from .base import Connector, ConnectorError
from .csv_file import CsvConnector
from .demo import DemoConnector
from .jira import JiraConnector
from .qtest import QTestConnector

REGISTRY: dict[str, type[Connector]] = {
    "jira": JiraConnector,
    "qtest": QTestConnector,
    "alm": AlmConnector,
    "csv": CsvConnector,
    "demo": DemoConnector,
}

__all__ = ["REGISTRY", "Connector", "ConnectorError"]
