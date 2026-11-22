"""Sift API: stateless, one resume per request. Runs as a Vercel Python function and locally.

    POST /api/score   one PDF + job JSON -> parse -> redact -> Jev -> scores + redacted JSON
    POST /api/jd      a job description file (PDF, DOCX or TXT) -> plain text
    GET  /api/health  live/mock mode and whether a key is set (never the key)

Nothing is written to disk and nothing is kept between requests. The ID -> file -> name map
lives only in the browser. Resume text, names and redacted JSON are never logged.
"""
from __future__ import annotations

import html
import io
import json
import logging
import os
import secrets
import re
import sys
import zipfile
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # so `shortlister` imports on Vercel as well as locally
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field, ValidationError, field_validator  # noqa: E402

from shortlister.jev import MODEL, JevScorer  # noqa: E402
from shortlister.parse import pdf_to_text  # noqa: E402
from shortlister.redact import REDACTION_MODE, redact  # noqa: E402

MAX_BYTES = 4 * 1024 * 1024  # Vercel caps request bodies at 4.5 MB
MAX_FILES = 100              # enforced by the client; reported here so both agree
CHIP_CUTOFF = 0.5
DEFAULT_RETRY_AFTER = 20

log = logging.getLogger("sift")
# pdfminer logs raw PDF text at DEBUG and HTTP clients can log payloads. Pin them so
# resume content can never reach the logs, whatever level the host runs at.
for _name in ("pdfminer", "pdfplumber", "typesafe_sdk", "httpx", "httpx2", "httpcore",
              "uvicorn.access", "python_multipart", "multipart"):
    logging.getLogger(_name).setLevel(logging.WARNING)

app = FastAPI(title="Sift", docs_url=None, redoc_url=None, openapi_url=None)


# ------------------------------------------------------------------ errors
def err(status: int, code: str, detail: str, **extra) -> HTTPException:
    return HTTPException(status, detail={"code": code, "detail": detail, **extra})


@app.exception_handler(HTTPException)
async def _http(_: Request, exc: HTTPException):
    d = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "detail": str(exc.detail)}
    headers = {"Retry-After": str(d["retry_after"])} if "retry_after" in d else None
    return JSONResponse(d, status_code=exc.status_code, headers=headers)


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.error("unhandled %s", type(exc).__name__)  # type only: never content
    return JSONResponse({"code": "server_error", "detail": "Something went wrong."}, status_code=500)


# ------------------------------------------------------------------ mode
def live_available() -> bool:
    """Open to everyone: live whenever the server has a key. With no key (local dev without
    .env) every response is mock and marked "mock": true, so made-up scores are never mistaken."""
    return bool(os.environ.get("TYPESAFE_API_KEY"))


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "mode": "live" if live_available() else "mock",
        "has_key": live_available(),
        "model": MODEL,
        "redaction": REDACTION_MODE,
        "max_mb": MAX_BYTES // (1024 * 1024),
        "max_files": MAX_FILES,
    }


# ------------------------------------------------------------------ job config
class MustHave(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    question: str = Field(min_length=3, max_length=500)

    @field_validator("key")
    @classmethod
    def _not_shortlist(cls, v: str) -> str:
        if v == "shortlist":
            raise ValueError("reserved key")
        return v


class Job(BaseModel):
    model_config = {"extra": "ignore"}
    role: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10, max_length=20000)
    shortlist_question: str = Field(
        "Based only on `resume`, should this candidate be shortlisted for a first interview "
        "for the role described in `job`?", min_length=10, max_length=1000)
    must_haves: List[MustHave] = Field(default_factory=list, max_length=12)
    threshold: float = Field(0.7, ge=0.3, le=0.9)

    @field_validator("must_haves")
    @classmethod
    def _unique(cls, v: List[MustHave]) -> List[MustHave]:
        if len({m.key for m in v}) != len(v):
            raise ValueError("duplicate must-have keys")
        return v


def parse_job(raw: str) -> Job:
    try:
        return Job.model_validate(json.loads(raw))
    except (ValueError, ValidationError):
        raise err(422, "bad_job", "The job settings are incomplete. Go back to step 1 and check them.") from None


# ------------------------------------------------------------------ Jev
def classify_error(exc: BaseException) -> tuple[int, str, str, dict]:
    """Map a Jev failure to (status, code, plain-language detail, extra). Never echoes str(exc)."""
    try:
        from typesafe_sdk import (TypeSafeAPIConnectionError, TypeSafeAPITimeoutError,
                                  TypeSafeAuthenticationError, TypeSafePermissionDeniedError,
                                  TypeSafeRateLimitError)
        if isinstance(exc, TypeSafeRateLimitError):
            ms = getattr(exc, "retry_after_ms", None)
            wait = max(1, round(ms / 1000)) if ms else DEFAULT_RETRY_AFTER
            return 429, "rate_limited", "The AI is busy (too many requests, code 429). Retrying shortly.", {"retry_after": wait}
        if isinstance(exc, (TypeSafeAuthenticationError, TypeSafePermissionDeniedError)):
            return 502, "auth", "The server's AI key isn't working. Ask whoever runs Sift to check TYPESAFE_API_KEY.", {}
        if isinstance(exc, TypeSafeAPITimeoutError):
            return 504, "timeout", "The AI took too long to answer. Try again.", {}
        if isinstance(exc, TypeSafeAPIConnectionError):
            return 502, "network", "The server couldn't reach the AI. Try again.", {}
    except ImportError:
        pass
    if getattr(exc, "status", None) == 429:
        return 429, "rate_limited", "The AI is busy (code 429). Retrying shortly.", {"retry_after": DEFAULT_RETRY_AFTER}
    return 502, "jev_error", "Something went wrong while scoring. Try again.", {}


def make_scorer(job: dict, mock: bool) -> JevScorer:
    """JevScorer as-is, but with a retry policy that fits inside one 60 s function call.
    429s are not retried here: the browser backs off instead, so the function never idles."""
    sc = JevScorer(job, mock=mock)  # raises SystemExit if the key is missing
    if not mock:
        from typesafe_sdk import RetryPolicy, TypeSafeClient
        sc.client = TypeSafeClient(model=MODEL, retry=RetryPolicy(
            max_retries=1, backoff_max=3.0, timeout=45.0, http_statuses={500, 502, 503, 504}))
    return sc


def new_id() -> str:
    return f"R-{secrets.token_hex(3).upper()}"


# ------------------------------------------------------------------ score
@app.post("/api/score")
async def score(file: UploadFile = File(...), job: str = Form(...)):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise err(413, "too_large", f"This file is larger than {MAX_BYTES // (1024 * 1024)} MB. Save a smaller PDF and add it again.")
    if not data.startswith(b"%PDF-"):
        raise err(415, "not_pdf", "This file isn't a PDF.")
    j = parse_job(job).model_dump()
    is_mock = not live_available()
    rid = new_id()

    try:
        text = pdf_to_text(io.BytesIO(data))
    except Exception:  # noqa: BLE001  (never log content)
        return _review(rid, is_mock, "This file couldn't be opened. Please read it yourself.")
    finally:
        del data

    payload, audit = redact(rid, text)
    del text
    name_guess = audit.get("candidate_name_guess") or ""
    base = {
        "id": rid, "mock": is_mock, "redacted": payload,
        "sections_found": audit.get("sections_found", []), "warnings": audit.get("warnings", []),
        "redactions": audit.get("redactions", {}), "name_guess": name_guess,
    }
    if audit.get("needs_human_review"):
        return {**_review(rid, is_mock, "We couldn't read the text in this file (it may be a scanned "
                          "image or an unusual layout). Please read it yourself."), **base}

    try:
        probs = make_scorer(j, is_mock).score(payload)
    except SystemExit:
        raise err(503, "missing_key", "The AI key isn't set on the server. Ask whoever runs Sift to set TYPESAFE_API_KEY.") from None
    except Exception as e:  # noqa: BLE001
        status, code, detail, extra = classify_error(e)
        log.warning("jev %s", code)
        raise err(status, code, detail, **extra) from None

    p = round(probs["shortlist"], 3)
    return {
        **base,
        "probability": p,
        "decision": "GO" if p >= j["threshold"] else "NO-GO",
        "must_haves": {m["key"]: {"prob": round(probs[m["key"]], 3), "pass": probs[m["key"]] >= CHIP_CUTOFF}
                       for m in j["must_haves"]},
        "needs_human_review": False,
        "reason": None,
    }


def _review(rid: str, is_mock: bool, reason: str) -> dict:
    return {"id": rid, "mock": is_mock, "probability": None, "decision": "REVIEW", "must_haves": {},
            "redacted": None, "sections_found": [], "warnings": [], "redactions": {}, "name_guess": "",
            "needs_human_review": True, "reason": reason}


# ------------------------------------------------------------------ job description upload
JD_MAX_CHARS = 20000  # same cap as Job.description


def docx_text(data: bytes) -> str:
    """Paragraph text from a .docx without extra dependencies: it is a zip of XML."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"</w:p>|<w:br/>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


@app.post("/api/jd")
async def job_description(file: UploadFile = File(...)):
    """Turn an uploaded JD into plain text for the description box. Nothing is stored or logged."""
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise err(413, "too_large", f"This file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    name = (file.filename or "").lower()
    try:
        if data.startswith(b"%PDF-"):
            text = pdf_to_text(io.BytesIO(data))
        elif data.startswith(b"PK") and (name.endswith(".docx") or not name):
            text = docx_text(data)
        elif name.endswith((".txt", ".md")) or (file.content_type or "").startswith("text/"):
            text = data.decode("utf-8", "replace")
        else:
            raise err(415, "bad_type", "Upload the job description as a PDF, Word (.docx) or text file.")
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001  (never log content)
        raise err(422, "unreadable", "We couldn't read that file. Paste the job description instead.") from None
    finally:
        del data
    text = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", text)).strip()
    if len(text) < 10:
        raise err(422, "empty", "We couldn't find any text in that file (it may be a scanned image). Paste the job description instead.")
    return {"text": text[:JD_MAX_CHARS], "truncated": len(text) > JD_MAX_CHARS}


# ------------------------------------------------------------------ local only: serve the build
_dist = ROOT / "web" / "dist"
if _dist.exists() and not os.environ.get("VERCEL"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
