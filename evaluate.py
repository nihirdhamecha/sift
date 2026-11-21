"""Compare Jev's decisions with your own labels.

    python evaluate.py --labels labels.csv [--run results/<timestamp>]

labels.csv: two columns, `file,label` where label is GO or NO-GO
(your own call on each resume, made BEFORE looking at Jev's output).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).parent


def latest_run() -> Path:
    runs = sorted(p for p in (ROOT / "results").iterdir() if (p / "shortlist.csv").exists())
    if not runs:
        raise SystemExit("No scored runs found. Run run.py first.")
    return runs[-1]


def metrics(pairs: list[tuple[bool, float]], t: float) -> dict:
    tp = sum(y and p >= t for y, p in pairs)
    fp = sum((not y) and p >= t for y, p in pairs)
    fn = sum(y and p < t for y, p in pairs)
    tn = sum((not y) and p < t for y, p in pairs)
    n = len(pairs)
    return {
        "threshold": t, "accuracy": (tp + tn) / n if n else 0,
        "precision": tp / (tp + fp) if tp + fp else 0,   # of Jev's GOs, how many you agree with
        "recall": tp / (tp + fn) if tp + fn else 0,      # of your GOs, how many Jev caught
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True, type=Path)
    ap.add_argument("--run", type=Path)
    args = ap.parse_args()
    run = args.run or latest_run()

    with args.labels.open() as f:
        labels = {r["file"].strip(): r["label"].strip().upper() == "GO" for r in csv.DictReader(f)}
    with (run / "shortlist.csv").open() as f:
        rows = [r for r in csv.DictReader(f) if r.get("probability")]

    pairs, misses = [], []
    for r in rows:
        if r["file"] in labels:
            y, p = labels[r["file"]], float(r["probability"])
            pairs.append((y, p))
            misses.append((r, y, p))
    if not pairs:
        raise SystemExit("No overlap between labels and results. Check the file names.")

    print(f"Run: {run.name}   resumes compared: {len(pairs)}\n")
    print(f"{'thresh':>6} {'acc':>6} {'prec':>6} {'recall':>6}   tp  fp  fn  tn")
    for t in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        m = metrics(pairs, t)
        print(f"{t:>6.1f} {m['accuracy']:>6.2f} {m['precision']:>6.2f} {m['recall']:>6.2f}"
              f"   {m['tp']:>2}  {m['fp']:>2}  {m['fn']:>2}  {m['tn']:>2}")

    print("\nBiggest disagreements (check these by hand):")
    misses.sort(key=lambda x: abs(x[1] - x[2]), reverse=True)
    for r, y, p in misses[:10]:
        if (p >= 0.5) != y:
            print(f"  {r['id']}  you={'GO' if y else 'NO-GO':5}  jev={p:.2f}  ({r['file']})")


if __name__ == "__main__":
    main()
