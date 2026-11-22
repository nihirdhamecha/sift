"""Shortlist decision policy. One overall score is too vague, so each must-have is its own check:

    GO            shortlist >= threshold and every must-have >= 0.5
    HUMAN REVIEW  shortlist >= threshold but exactly one must-have is below 0.5 (the borderline case)
    NO-GO         otherwise (shortlist below threshold, or two or more must-haves fail)

Resumes that couldn't be parsed are also HUMAN REVIEW, flagged separately by the caller.
"""
from __future__ import annotations

from typing import Mapping

MUST_HAVE_CUTOFF = 0.5

GO, REVIEW, NO_GO = "GO", "HUMAN REVIEW", "NO-GO"


def failed_must_haves(must_haves: Mapping[str, float]) -> list[str]:
    return [k for k, p in must_haves.items() if p < MUST_HAVE_CUTOFF]


def decide(shortlist: float, must_haves: Mapping[str, float], threshold: float) -> str:
    """must_haves: {key: probability}. Returns GO, HUMAN REVIEW or NO-GO."""
    if shortlist < threshold:
        return NO_GO
    failed = len(failed_must_haves(must_haves))
    if failed == 0:
        return GO
    return REVIEW if failed == 1 else NO_GO
