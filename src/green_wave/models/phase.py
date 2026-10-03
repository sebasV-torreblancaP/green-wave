from enum import StrEnum


class Phase(StrEnum):
    RED = "R"
    GREEN = "V"
    YELLOW = "A"


class BoundaryKind(StrEnum):
    RED_TO_GREEN = "R→V"
    GREEN_TO_YELLOW = "V→A"
    YELLOW_TO_RED = "A→R"

