"""
Measures extraction accuracy against the known true prices (samples/truth/), i.e. the brief's
acceptance criterion: at least 98% of rows correct, and NO price that isn't in the source.

    python evaluate.py              # reads all 6 sample lists (cached after the first run)
    python evaluate.py --fresh      # ignore the cache and read everything again with the AI

Exit code 0 = passes the brief's bar, 1 = doesn't.
"""

import argparse
import csv
import shutil
import sys

import pricesync as ps

TRUTH = ps.HERE / "samples" / "truth"


def load_truth(path, source):
    """True rows, identified exactly as the tool identifies products (code, or printed text in a PDF)."""
    pages = ps.pdf_pages(source) if source.suffix.lower() == ".pdf" else []
    truth = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            row = ps.Row(r["code"], r["description"], r["unit"], float(r["price"]))
            if not row.code:
                row.source = next((s for _, text in pages if (s := ps.find_line(row, text)) is not None), "")
            truth[row.key] = (row.price, row.description)
    return truth


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fresh", action="store_true", help="re-read every list with the AI (costs about $0.02)")
    args = p.parse_args()
    if args.fresh and ps.EXTRACTED.exists():
        shutil.rmtree(ps.EXTRACTED)

    print(f"{'Supplier':<32} {'Date':<11} {'True':>5} {'Right':>6} {'Wrong':>6} {'Missed':>7} {'Aside':>6} {'Accuracy':>9}")
    totals = {"true": 0, "right": 0, "wrong": 0, "cost": 0.0}
    try:
        for truth_file in sorted(TRUTH.glob("*/*.csv")):
            supplier, date = truth_file.parent.name, truth_file.stem
            source = next((ps.LISTS / supplier).glob(f"{date}.*"))
            expected = load_truth(truth_file, source)
            pl = ps.read_list(source, supplier)
            got = {r.key: r for r in pl.rows}
            right = sum(1 for k, r in got.items() if k in expected and expected[k][0] == r.price)
            wrong_price = [(r, expected[k][0]) for k, r in got.items() if k in expected and expected[k][0] != r.price]
            extra = [r for k, r in got.items() if k not in expected]       # not a real product: counts as wrong
            missed = [expected[k][1] for k in expected if k not in got]
            wrong = len(wrong_price) + len(extra)
            print(f"{supplier:<32} {date:<11} {len(expected):>5} {right:>6} {wrong:>6} {len(missed):>7} "
                  f"{len(pl.rejected):>6} {right / len(expected):>8.1%}")
            for r, true in wrong_price:                                     # explain every miss
                print(f"    WRONG PRICE  {ps.label(r)[:50]:<50} read {ps.fmt(r.price)}, true {ps.fmt(true)}")
            for r in extra:
                print(f"    NOT ON LIST  {ps.label(r)[:50]:<50} {ps.fmt(r.price)}  (printed: '{r.source}')")
            for description in missed:
                print(f"    MISSED       {description}")
            for r in pl.rejected:
                print(f"    SET ASIDE    {ps.label(r)[:50]:<50} {r.note}")
            totals["true"] += len(expected)
            totals["right"] += right
            totals["wrong"] += wrong
            totals["cost"] += pl.cost_usd
    except ps.SyncError as err:
        sys.exit(f"Problem: {err}")

    accuracy = totals["right"] / totals["true"]
    ok = accuracy >= 0.98 and totals["wrong"] == 0
    print(f"\nOverall: {totals['right']}/{totals['true']} correct = {accuracy:.1%}, "
          f"{totals['wrong']} wrong prices used | AI cost ${totals['cost']:.4f}")
    print("PASS: meets the brief (>= 98% correct, no wrong price used)" if ok else
          "FAIL: below the brief's bar. Look at the 'set aside' rows in extracted/")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
