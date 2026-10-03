from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from .trace import SignalTrace


class TransitionStatus(StrEnum):
    COMPLETED = "completed"
    INCOMPLETE_LIMIT = "incomplete_limit"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class TransitionStep:
    intersection_id: str
    local_cycle: int
    applied_at_s: int
    previous_green_s: int
    next_green_s: int
    previous_fitness: float
    next_fitness: float
    optimizer_generations: int
    evaluated_candidates: int
    optimizer_reason: str


@dataclass(frozen=True, slots=True)
class TransitionResult:
    status: TransitionStatus
    started_at_s: int
    ended_at_s: int
    steps: tuple[TransitionStep, ...]
    final_green_s: Mapping[str, int]
    final_fitness: Mapping[str, float]
    traces: Mapping[str, SignalTrace]
    method: str
    policy: str
    boundary_metric: str
    optimizer_parameters: Mapping[str, object] = field(default_factory=dict)
    diagnostics: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "final_green_s", MappingProxyType(dict(self.final_green_s)))
        object.__setattr__(self, "final_fitness", MappingProxyType(dict(self.final_fitness)))
        object.__setattr__(self, "traces", MappingProxyType(dict(self.traces)))
        object.__setattr__(self, "optimizer_parameters", MappingProxyType(dict(self.optimizer_parameters)))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))
