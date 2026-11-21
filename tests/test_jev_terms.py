"""Requirement wording sent to Jev: abbreviations spelled out, old wording upgraded.

    .venv/bin/python -m pytest tests/test_jev_terms.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shortlister.jev import REQ_PREFIX, REQ_SUFFIX, expand_terms, job_text, requirement_question  # noqa: E402


def test_abbreviations_are_spelled_out():
    assert "direct-to-consumer" in expand_terms("is a D2C PM")
    assert "product manager" in expand_terms("is a D2C PM")
    assert "business-to-business" in expand_terms("has B2B SaaS experience")
    assert expand_terms("5+ years in B2B2C").endswith("(business-to-business-to-consumer)")


def test_expansion_is_idempotent_and_leaves_other_words():
    once = expand_terms("Owns P&L for D2C brands")
    assert expand_terms(once) == once
    assert expand_terms("Uses SQL and Excel") == "Uses SQL and Excel"
    assert expand_terms("SPMs and D2Clike") == "SPMs and D2Clike"  # only whole terms


def test_old_wording_is_upgraded():
    old = "Based only on `resume`, does the candidate meet this requirement for the role in `job`: is a D2C PM?"
    q = requirement_question(old)
    assert q.startswith(REQ_PREFIX) and q.endswith(REQ_SUFFIX) and "direct-to-consumer" in q


def test_job_description_is_expanded_too():
    assert "direct-to-consumer" in job_text({"role": "PM", "description": "Lead our D2C app"})
