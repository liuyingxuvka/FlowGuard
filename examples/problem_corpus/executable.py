"""Executable review entry point for the real software problem corpus.

Phase 11 uses workflow-family-specific real model bindings. The old Phase 10.8
generic corpus template is intentionally not used by this entry point.
"""

from __future__ import annotations

from typing import Iterable

from flowguard.executable import ExecutableCaseResult, ExecutableCorpusReport

from .matrix import build_problem_corpus
from .real_models import execute_real_model_case, execute_real_model_cases, review_real_model_corpus
from flowguard.corpus import ProblemCase, ProblemCorpus


def execute_problem_case(case: ProblemCase) -> ExecutableCaseResult:
    """Run one ProblemCase through its real domain model binding."""

    return execute_real_model_case(case)


def execute_problem_cases(cases: Iterable[ProblemCase]) -> tuple[ExecutableCaseResult, ...]:
    return execute_real_model_cases(cases)


def review_executable_corpus(corpus: ProblemCorpus | None = None) -> ExecutableCorpusReport:
    return review_real_model_corpus(corpus or build_problem_corpus())


__all__ = [
    "execute_problem_case",
    "execute_problem_cases",
    "review_executable_corpus",
]
