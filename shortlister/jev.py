"""Thin wrapper around Jev. One call per resume: a shortlist Noul plus must-have Nouls.

Set TYPESAFE_API_KEY in your environment. Use mock=True to dry-run the pipeline
without a key (scores are FAKE and marked as such).
"""
from __future__ import annotations

import hashlib
import json
import os
import re

MODEL = os.environ.get("JEV_MODEL", "jev-1.13.0")  # pinned so results are reproducible


# Jev reads requirements literally. "is a D2C PM" scored 0.20 on a consumer-app PM's resume
# that never uses the word "D2C"; spelled out it scored 0.79, while non-matching resumes
# stayed low. So hiring abbreviations are expanded before Jev sees them.
GLOSSARY = {
    "D2C": "direct-to-consumer: a product offered directly to individual consumers",
    "DTC": "direct-to-consumer: a product offered directly to individual consumers",
    "B2C": "business-to-consumer",
    "B2B": "business-to-business",
    "B2B2C": "business-to-business-to-consumer",
    "SaaS": "software sold as a subscription service",
    "GTM": "go-to-market",
    "PM": "product manager",
    "APM": "associate product manager",
    "PMM": "product marketing manager",
    "P&L": "profit and loss",
    "ARR": "annual recurring revenue",
    "MRR": "monthly recurring revenue",
    "MAU": "monthly active users",
    "DAU": "daily active users",
    "CRM": "customer relationship management",
    "FMCG": "fast-moving consumer goods",
    "CPG": "consumer packaged goods",
    "BFSI": "banking, financial services and insurance",
    "NBFC": "non-banking financial company",
}
_TERM = re.compile(r"(?<![\w&])(" + "|".join(re.escape(k) for k in sorted(GLOSSARY, key=len, reverse=True)) + r")s?(?![\w&])(?!\s*\()")


def expand_terms(text: str) -> str:
    """'is a D2C PM' -> 'is a D2C (direct-to-consumer: ...) PM (product manager)'. Idempotent."""
    return _TERM.sub(lambda m: f"{m.group(0)} ({GLOSSARY[m.group(1)]})", text)


# Requirement wording. Jev also matched better when told that different words count.
_OLD_PREFIX = "Based only on `resume`, does the candidate meet this requirement for the role in `job`: "
REQ_PREFIX = "Based only on `resume`, does the candidate meet this requirement: "
REQ_SUFFIX = ("? Count it as met if the resume shows it, even when it is described in different words "
              "or without the same abbreviation.")


def requirement_question(question: str) -> str:
    """Normalise a must-have question: upgrade the old wording and expand abbreviations."""
    if question.startswith(_OLD_PREFIX):
        question = REQ_PREFIX + question[len(_OLD_PREFIX):].rstrip("?") + REQ_SUFFIX
    return expand_terms(question)


def build_questions(job: dict):
    from typesafe_sdk import Noul

    questions = {"shortlist": Noul(instructions=job["shortlist_question"])}
    for mh in job.get("must_haves", []):
        questions[mh["key"]] = Noul(instructions=requirement_question(mh["question"]))
    return questions


def job_text(job: dict) -> str:
    return expand_terms(f"Role: {job['role']}\n\n{job['description']}")


class JevScorer:
    def __init__(self, job: dict, mock: bool = False):
        self.job = job
        self.mock = mock
        self.keys = ["shortlist"] + [m["key"] for m in job.get("must_haves", [])]
        if not mock:
            from typesafe_sdk import RetryPolicy, TypeSafeClient

            if not os.environ.get("TYPESAFE_API_KEY"):
                raise SystemExit("TYPESAFE_API_KEY is not set. Export it, or run with --mock.")
            self.client = TypeSafeClient(
                model=MODEL, retry=RetryPolicy(max_retries=5, backoff_max=20.0, timeout=120.0))
            self.questions = build_questions(job)

    def score(self, resume) -> dict[str, float]:
        """resume: the redacted payload (dict) or raw text (str, swap test only)."""
        if self.mock:
            return self._mock(resume)
        state = {"job": job_text(self.job), "resume": resume}
        resp = self.client.system_one(state=state, questions=self.questions)
        return {k: float(resp.nouls[k].noul) for k in self.keys}

    def _mock(self, resume) -> dict[str, float]:
        blob = json.dumps(resume, sort_keys=True) if isinstance(resume, dict) else resume
        out = {}
        for k in self.keys:
            h = hashlib.sha256((k + blob).encode()).hexdigest()
            out[k] = round(int(h[:8], 16) / 0xFFFFFFFF, 3)
        return out
