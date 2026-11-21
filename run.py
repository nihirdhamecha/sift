"""Shortlist a folder of resume PDFs with Jev.

    python run.py                      # real Jev (needs TYPESAFE_API_KEY)
    python run.py --mock               # dry run, fake scores
    python run.py --redact-only        # just build redacted JSON to inspect for leaks

Outputs (results/<timestamp>/):
    redacted/R-001.json   exactly what Jev saw
    audit.csv             what was found/removed per resume
    scores.csv            ID-only scores (no names)
    shortlist.csv         scores mapped back to file + candidate name, sorted
private/id_map.csv        ID -> file -> name. Never sent to Jev.
"""
from __future__ import annotations

import argparse
import csv
import json
import secrets
from datetime import datetime
from pathlib import Path

from shortlister.jev import JevScorer
from shortlister.parse import pdf_to_text
from shortlister.redact import redact

ROOT = Path(__file__).parent


def load_or_create_id_map(pdfs: list[Path], map_path: Path) -> dict[str, str]:
    """Stable random IDs per file, so re-runs and eval line up."""
    mapping: dict[str, str] = {}
    if map_path.exists():
        with map_path.open() as f:
            mapping = {r["file"]: r["id"] for r in csv.DictReader(f)}
    used = set(mapping.values())
    for pdf in pdfs:
        if pdf.name not in mapping:
            while (rid := f"R-{secrets.randbelow(9000) + 1000}") in used:
                pass
            mapping[pdf.name] = rid
            used.add(rid)
    return mapping


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resumes", default=ROOT / "resumes", type=Path)
    ap.add_argument("--job", default=ROOT / "config" / "job.json", type=Path)
    ap.add_argument("--mock", action="store_true", help="fake scores, no API key needed")
    ap.add_argument("--redact-only", action="store_true")
    args = ap.parse_args()

    job = json.loads(args.job.read_text())
    threshold = float(job.get("threshold", 0.7))
    pdfs = sorted(args.resumes.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs in {args.resumes}")

    out = ROOT / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / "redacted").mkdir(parents=True)
    map_path = ROOT / "private" / "id_map.csv"
    map_path.parent.mkdir(exist_ok=True)
    id_map = load_or_create_id_map(pdfs, map_path)

    scorer = None if args.redact_only else JevScorer(job, mock=args.mock)
    names, audits, scores = {}, [], []

    for i, pdf in enumerate(pdfs, 1):
        rid = id_map[pdf.name]
        text = pdf_to_text(pdf)
        payload, audit = redact(rid, text)
        names[rid] = audit.pop("candidate_name_guess")
        audit["redactions"] = json.dumps(audit["redactions"])
        audits.append(audit)
        (out / "redacted" / f"{rid}.json").write_text(json.dumps(payload, indent=2))

        if scorer is None:
            continue
        if audit["needs_human_review"]:
            scores.append({"id": rid, "decision": "HUMAN REVIEW (parse failed)"})
            print(f"[{i}/{len(pdfs)}] {rid}: could not parse, sent to human review")
            continue
        s = scorer.score(payload)
        row = {"id": rid, "probability": round(s["shortlist"], 3),
               "decision": "GO" if s["shortlist"] >= threshold else "NO-GO"}
        row.update({k: round(v, 3) for k, v in s.items() if k != "shortlist"})
        scores.append(row)
        print(f"[{i}/{len(pdfs)}] {rid}: {row['decision']} ({row['probability']})")

    # private map (written after run so names are filled in)
    with map_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "file", "candidate_name"])
        w.writeheader()
        for file, rid in sorted(id_map.items(), key=lambda kv: kv[1]):
            w.writerow({"id": rid, "file": file, "candidate_name": names.get(rid, "")})

    _write_csv(out / "audit.csv", audits)
    if scorer is None:
        print(f"Redacted JSON written to {out/'redacted'}. Inspect it for leaks.")
        return

    _write_csv(out / "scores.csv", scores)
    file_of = {rid: file for file, rid in id_map.items()}
    final = [{"candidate_name": names.get(r["id"], ""), "file": file_of[r["id"]], **r} for r in scores]
    final.sort(key=lambda r: r.get("probability", -1), reverse=True)
    _write_csv(out / "shortlist.csv", final)

    go = sum(r["decision"] == "GO" for r in scores)
    tag = " [MOCK SCORES - NOT REAL]" if args.mock else ""
    print(f"\n{go}/{len(scores)} shortlisted at threshold {threshold}{tag}")
    print(f"Results: {out}")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
