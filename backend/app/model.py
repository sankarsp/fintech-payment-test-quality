"""The common data model.

Every connector (Jira, qTest, ALM, CSV, ...) turns its own records into these
objects. The reports only ever read these objects, so every report works the
same way for every tool.

The value lists below match the article "Sell me this defect" on
paymentconsultant.top: four severities, the bug life cycle statuses,
12 categories, test levels, sources, channels and interfaces.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    S1 = "S1"  # Critical: money, data or security at risk, or service down
    S2 = "S2"  # High: a main feature broken, no easy workaround
    S3 = "S3"  # Medium: workaround exists
    S4 = "S4"  # Low: cosmetic


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Status(str, Enum):
    """Bug life cycle statuses."""
    NEW = "New"
    ASSIGNED = "Assigned"
    OPEN = "Open"            # developer is working on it
    FIXED = "Fixed"
    RETEST = "Retest"
    REOPENED = "Reopened"
    VERIFIED = "Verified"
    CLOSED = "Closed"
    REJECTED = "Rejected"    # not a real bug: duplicate, test data error, works as designed
    DEFERRED = "Deferred"    # moved to a later release

    @property
    def is_open(self) -> bool:
        return self not in (Status.CLOSED, Status.REJECTED, Status.VERIFIED)


class Category(str, Enum):
    FUNCTIONAL = "Functional"
    DATA = "Data"
    ENVIRONMENT = "Environment"
    REQUIREMENT = "Requirement"
    INTERFACE = "Interface"
    USABILITY = "Usability"
    COMPATIBILITY = "Compatibility"
    PERFORMANCE = "Performance"
    SECURITY = "Security"
    ACCESSIBILITY = "Accessibility"
    NOT_REPRODUCIBLE = "Not reproducible"
    TESTER_ERROR = "Tester error"
    UNKNOWN = "Unknown"


class TestLevel(str, Enum):
    UNIT = "Unit"
    SYSTEM = "System"
    SIT = "SIT"
    E2E = "E2E"
    UAT = "UAT"
    PENNY = "Penny"
    PRODUCTION = "Production"
    UNKNOWN = "Unknown"


# Order matters: a bug found at a later level "leaked" past the earlier ones.
LEVEL_ORDER = [TestLevel.UNIT, TestLevel.SYSTEM, TestLevel.SIT, TestLevel.E2E,
               TestLevel.UAT, TestLevel.PENNY, TestLevel.PRODUCTION]


class Source(str, Enum):
    """Which kind of testing found the bug."""
    MANUAL = "Manual"
    AUTOMATION = "Automation"
    PERFORMANCE = "Performance"
    SECURITY = "Security"
    COMPLIANCE = "Compliance"
    PRODUCTION = "Production"
    UNKNOWN = "Unknown"


class Channel(str, Enum):
    MOBILE = "Mobile app"
    WEB = "Web"
    API = "APIs and backend"
    LEGACY = "Legacy"
    UNKNOWN = "Unknown"


class Interface(str, Enum):
    NONE = "None"
    UPSTREAM = "Upstream"
    DOWNSTREAM = "Downstream"
    EXTERNAL = "External"
    LEGACY = "Legacy"


class Defect(BaseModel):
    """One bug, in the same shape whatever tool it came from."""
    id: str = Field(description="Unique id: '<tool>:<key>'")
    tool: str
    key: str
    title: str = ""
    severity: Severity = Severity.S3
    priority: Priority = Priority.P3
    status: Status = Status.NEW
    category: Category = Category.UNKNOWN
    found_in: TestLevel = TestLevel.UNKNOWN
    source: Source = Source.UNKNOWN
    channel: Channel = Channel.UNKNOWN
    interface: Interface = Interface.NONE
    application: str = ""
    owner_team: str = ""
    epic: str = ""
    feature: str = ""
    story: str = ""
    sprint: str = ""
    created: datetime
    closed: datetime | None = None
    reopen_count: int = 0
    exploratory: bool = False  # found in an exploratory session, not a planned test
    raw_unmapped: dict[str, str] = Field(default_factory=dict,
                                         description="Values the mapping did not recognise")


class TestRun(BaseModel):
    """One test execution."""
    id: str
    tool: str
    key: str
    status: str  # Passed / Failed / Blocked / Not run
    level: TestLevel = TestLevel.UNKNOWN
    planned: bool = True  # False = exploratory session
    story: str = ""
    feature: str = ""
    epic: str = ""
    executed: datetime | None = None


class Dataset(BaseModel):
    defects: list[Defect] = Field(default_factory=list)
    runs: list[TestRun] = Field(default_factory=list)

    def extend(self, other: "Dataset") -> None:
        self.defects.extend(other.defects)
        self.runs.extend(other.runs)
