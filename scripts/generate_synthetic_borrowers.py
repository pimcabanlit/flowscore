"""Write the synthetic demo borrowers (spec docs/specs/02-synthetic-borrowers.md, S2-R4).

    $env:PYTHONPATH="src"; python scripts\\generate_synthetic_borrowers.py [--seed 2026] [--out demo\\synthetic]

DEMO ONLY: fictional borrowers, no outcomes, never research evidence (D1, hard rule 9).
The same seed always writes byte-identical files; tests/test_synthetic.py checks that the
committed demo/synthetic/ matches the default seed.
"""
import argparse
from pathlib import Path

from flowscore.synthetic import DEFAULT_SEED, write

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"random seed (default {DEFAULT_SEED})")
    ap.add_argument("--out", type=Path, default=ROOT / "demo" / "synthetic", help="output folder")
    args = ap.parse_args(argv)
    for path in write(args.out, args.seed):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
