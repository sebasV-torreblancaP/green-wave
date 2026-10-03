from .interfaces import OptimizationResult, ScoreFunction, checked_score
from .search_context import SearchContext


class ExhaustiveOptimizer:
    """Deterministic one-step reference search, not a genetic algorithm.

    Equal scores retain the incumbent. The caller supplies a fully defined
    fitness function; this class makes no assumptions about phase anchoring.
    """

    def search(self, context: SearchContext, score: ScoreFunction) -> OptimizationResult:
        domain = context.feasible_greens
        current = context.current_green_s
        best_green = current
        best_score = checked_score(score(current))
        for green in domain.values():
            if green == current:
                continue
            candidate_score = checked_score(score(green))
            if candidate_score > best_score:
                best_green, best_score = green, candidate_score
        return OptimizationResult(best_green, best_score, len(domain), "exhaustive")

