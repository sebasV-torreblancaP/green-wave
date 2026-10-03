class GreenWaveError(Exception):
    """Base error for invalid inputs or unresolved model contracts."""


class ConfigurationError(GreenWaveError):
    """A configuration field or cross-reference is invalid."""


class ModelDecisionRequired(GreenWaveError):
    """The requested operation depends on a decision still open in the plan."""


class InvalidCandidate(GreenWaveError):
    """A proposed green duration violates the current search constraints."""

