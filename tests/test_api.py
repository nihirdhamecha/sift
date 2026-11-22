"""Stateless Vercel API: privacy, modes and error handling. Runs in mock mode with no key."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.index as sift
from shortlister.parse import pdf_to_text
from shortlister.redact import guess_name, redact, split_sections

SAMPLES = sorted((Path(__file__).parent / "sample_resumes").glob("*.pdf"))
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
JOB = {
    "role": "Product Manager",
    "description": "Own the roadmap for a consumer fintech app and work with engineering.",
    "must_haves": [{"key": "pm_exp", "question": "Based only on `resume`, does the candidate meet this requirement: has product management experience?"}],
    "threshold": 0.7,
}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)


@pytest.fixture
def client():
    return TestClient(sift.app)


def score(client, path: Path, job=JOB):
    return client.post("/api/score", files={"file": ("resume.pdf", path.read_bytes(), "application/pdf")},
                       data={"job": json.dumps(job)})


class Fake:
    def score(self, _):
        return {"shortlist": 0.9, "pm_exp": 0.8}


def identity(path: Path) -> dict:
    """The identifying values in a sample, pulled from its raw text."""
    text = pdf_to_text(path)
    name = guess_name(split_sections(text)[0])
    assert name, f"no name found in {path.name}"
    return {"name_tokens": [t for t in name.split() if len(t) > 2], "emails": EMAIL.findall(text),
            "phones": [re.sub(r"\D", "", p)[-10:] for p in PHONE.findall(text)], "file": path.name}


def leaks(blob: str, ident: dict) -> list[str]:
    found = [t for t in ident["name_tokens"] if re.search(rf"\b{re.escape(t)}\b", blob, re.I)]
    found += [e for e in ident["emails"] if e.lower() in blob.lower()]
    in_blob = {re.sub(r"\D", "", m)[-10:] for m in PHONE.findall(blob)}
    found += [p for p in ident["phones"] if p in in_blob]
    if ident["file"] in blob:
        found.append(ident["file"])
    return found


# ------------------------------------------------------------------ privacy
@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_redacted_json_has_no_name_email_or_phone(path):
    """Name mode (the default): city and college are sent on purpose; name and contact never."""
    ident = identity(path)
    payload, _ = redact("R-TEST", pdf_to_text(path))
    assert leaks(json.dumps(payload), ident) == []


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_full_mode_also_hides_city_and_college(path):
    payload, _ = redact("R-TEST", pdf_to_text(path), mode="full")
    blob = json.dumps(payload).lower()
    assert leaks(blob, identity(path)) == []
    for word in ("pune", "hyderabad", "lucknow", "maharashtra", "indian institute", "university"):
        assert word not in blob


def test_each_response_carries_only_its_own_name(client):
    idents = {p: identity(p) for p in SAMPLES}
    ids = set()
    for p in SAMPLES:
        r = score(client, p)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mock"] is True
        assert re.fullmatch(r"R-[0-9A-F]{6}", body["id"])
        ids.add(body["id"])
        own = idents[p]
        assert set(own["name_tokens"]) <= set(body["name_guess"].split())
        rest = json.dumps({k: v for k, v in body.items() if k != "name_guess"})
        assert leaks(rest, own) == [], "name/contact outside name_guess"
        for other in SAMPLES:
            if other != p:
                assert leaks(r.text, idents[other]) == [], f"{other.name} leaked into {p.name}'s response"
        assert "sample_" not in r.text  # the server never learns filenames
        assert not any(i in r.text for i in ids - {body["id"]})  # nor other resumes' IDs
    assert len(ids) == len(SAMPLES)


def test_ids_are_random_per_request(client):
    a, b = (score(client, SAMPLES[0]).json()["id"] for _ in range(2))
    assert a != b


def test_resume_content_never_logged(client, caplog):
    caplog.set_level(logging.DEBUG)
    for p in SAMPLES:
        score(client, p)
    score(client, SAMPLES[0], job={"role": "x"})  # an error path too
    for p in SAMPLES:
        assert leaks(caplog.text, identity(p)) == []
    assert "Swiftpay" not in caplog.text and "onboarding" not in caplog.text


# ------------------------------------------------------------------ modes
def test_health_never_returns_key(client, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts_secret_123456")
    r = client.get("/api/health")
    assert r.json()["mode"] == "live" and r.json()["has_key"] is True
    assert "ts_secret" not in r.text


def test_no_key_means_marked_mock(client):
    assert client.get("/api/health").json()["mode"] == "mock"
    assert score(client, SAMPLES[0]).json()["mock"] is True


def test_open_to_all_with_a_key(client, monkeypatch):
    """No password or demo switch: with a key, every request is scored live."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts_x")
    monkeypatch.setenv("DEMO_MODE", "true")       # old switches are ignored
    monkeypatch.setenv("DEMO_PASSWORD", "pw")
    monkeypatch.setattr(sift, "make_scorer", lambda job, mock: Fake() if not mock else pytest.fail("mocked"))
    body = score(client, SAMPLES[0]).json()
    assert body["mock"] is False and body["decision"] == "GO" and body["must_haves"]["pm_exp"]["pass"] is True


# ------------------------------------------------------------------ errors
def test_too_large_is_413(client):
    big = b"%PDF-1.4\n" + b"0" * (4 * 1024 * 1024)
    r = client.post("/api/score", files={"file": ("r.pdf", big, "application/pdf")}, data={"job": json.dumps(JOB)})
    assert r.status_code == 413 and "4 MB" in r.json()["detail"]


def test_not_a_pdf_is_415(client):
    r = client.post("/api/score", files={"file": ("r.pdf", b"hello", "application/pdf")}, data={"job": json.dumps(JOB)})
    assert r.status_code == 415


def test_parse_failure_goes_to_human_review(client):
    r = client.post("/api/score", files={"file": ("r.pdf", b"%PDF-1.4 garbage", "application/pdf")}, data={"job": json.dumps(JOB)})
    assert r.status_code == 200
    assert r.json()["needs_human_review"] is True and r.json()["decision"] == "HUMAN REVIEW" and r.json()["reason"]


def test_bad_job_is_422(client):
    assert score(client, SAMPLES[0], job={"role": ""}).json()["code"] == "bad_job"


def test_rate_limit_returns_retry_after(client, monkeypatch):
    import httpx2
    from typesafe_sdk import TypeSafeRateLimitError
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts_x")

    class Busy:
        def score(self, _):
            raise TypeSafeRateLimitError(429, {}, httpx2.Headers({"retry-after": "7"}))
    monkeypatch.setattr(sift, "make_scorer", lambda job, mock: Busy())
    r = score(client, SAMPLES[0])
    assert r.status_code == 429 and r.json()["retry_after"] == 7 and r.headers["Retry-After"] == "7"


def test_missing_key_is_visible(client, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts_x")

    def boom(job, mock):
        raise SystemExit("no key")
    monkeypatch.setattr(sift, "make_scorer", boom)
    r = score(client, SAMPLES[0])
    assert r.status_code == 503 and r.json()["code"] == "missing_key"


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.stem)
def test_leak_detector_catches_raw_text(path):
    """Control: the checks above would fail if the name, email or phone were present."""
    found = leaks(pdf_to_text(path), identity(path))
    assert any(t in found for t in identity(path)["name_tokens"]) and identity(path)["emails"][0] in found
    assert identity(path)["phones"][0] in found


# ------------------------------------------------------------------ job description upload
def _docx(paragraphs: list[str]) -> bytes:
    import io
    import zipfile
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f'<w:document xmlns:w="x"><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


def jd(client, name, data, ctype="application/octet-stream"):
    return client.post("/api/jd", files={"file": (name, data, ctype)})


def test_jd_from_pdf(client):
    r = jd(client, "jd.pdf", SAMPLES[0].read_bytes(), "application/pdf")
    assert r.status_code == 200 and "Product Manager" in r.json()["text"]


def test_jd_from_docx(client):
    r = jd(client, "jd.docx", _docx(["Senior PM, Payments", "Own the checkout roadmap &amp; growth."]))
    assert r.status_code == 200
    assert r.json()["text"] == "Senior PM, Payments\nOwn the checkout roadmap & growth."


def test_jd_from_text(client):
    r = jd(client, "jd.txt", "Sales Manager\n\n\n\nLead a team of six.".encode(), "text/plain")
    assert r.json() == {"text": "Sales Manager\n\nLead a team of six.", "truncated": False}


def test_jd_long_text_is_truncated(client):
    r = jd(client, "jd.txt", ("word " * 6000).encode(), "text/plain")
    assert r.json()["truncated"] is True and len(r.json()["text"]) == 20000


def test_jd_rejects_other_files(client):
    assert jd(client, "jd.png", b"\x89PNG....", "image/png").status_code == 415
    assert jd(client, "jd.txt", b"   ", "text/plain").json()["code"] == "empty"
    assert jd(client, "jd.pdf", b"%PDF-1.4 broken", "application/pdf").status_code == 422


# ------------------------------------------------------------------ decision policy
from shortlister.policy import decide  # noqa: E402


@pytest.mark.parametrize("shortlist,must,expected", [
    (0.80, {"a": 0.9, "b": 0.6}, "GO"),                   # high and every must-have met
    (0.70, {"a": 0.5, "b": 0.5}, "GO"),                   # boundaries are inclusive
    (0.80, {}, "GO"),                                     # no must-haves: shortlist alone
    (0.85, {"a": 0.9, "b": 0.3}, "HUMAN REVIEW"),         # high but exactly one fails
    (0.85, {"a": 0.2, "b": 0.3}, "NO-GO"),                # two fail
    (0.60, {"a": 0.9, "b": 0.9}, "NO-GO"),                # below threshold, even if all met
    (0.69, {"a": 0.2}, "NO-GO"),
])
def test_policy(shortlist, must, expected):
    assert decide(shortlist, must, 0.7) == expected


def test_api_applies_policy(client, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts_x")
    job = {**JOB, "must_haves": JOB["must_haves"] + [{"key": "sql", "question": "Knows SQL"}]}

    def run(probs):
        class S:
            def score(self, _):
                return probs
        monkeypatch.setattr(sift, "make_scorer", lambda j, mock: S())
        return score(client, SAMPLES[0], job=job).json()

    assert run({"shortlist": 0.9, "pm_exp": 0.8, "sql": 0.7})["decision"] == "GO"
    r = run({"shortlist": 0.9, "pm_exp": 0.8, "sql": 0.2})
    assert r["decision"] == "HUMAN REVIEW" and r["failed_must_haves"] == ["sql"] and r["needs_human_review"] is False
    assert run({"shortlist": 0.9, "pm_exp": 0.1, "sql": 0.2})["decision"] == "NO-GO"
    assert run({"shortlist": 0.5, "pm_exp": 0.9, "sql": 0.9})["decision"] == "NO-GO"


def test_unreadable_file_is_human_review(client):
    r = client.post("/api/score", files={"file": ("r.pdf", b"%PDF-1.4 garbage", "application/pdf")}, data={"job": json.dumps(JOB)}).json()
    assert r["decision"] == "HUMAN REVIEW" and r["needs_human_review"] is True and r["probability"] is None
