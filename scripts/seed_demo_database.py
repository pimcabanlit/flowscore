"""Load the synthetic demo borrowers (demo/synthetic/) into the database (spec S3-R12).

    $env:PYTHONPATH="src"; $env:FLOWSCORE_DATABASE_URL="..."; alembic upgrade head
    python scripts\\seed_demo_database.py

One batch per borrower, covering history_start (inclusive) to as_of (exclusive). Before anything
is written, every borrower must be marked synthetic and every row must pass schema.validate()
with amounts of at most 2 decimal places. A second run changes nothing: a borrower already in the
database is skipped when its stored transactions match the files, and reported (never
overwritten) when they differ. Prints borrower ids and counts only, never amounts.
"""
import asyncio
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))            # for backend.app

from flowscore.schema import validate                                    # noqa: E402
from flowscore_demo.synthetic import read                                # noqa: E402

from backend.app.borrowers.models import Borrower                        # noqa: E402
from backend.app.core.db import make_engine, make_sessionmaker           # noqa: E402
from backend.app.core.settings import Settings                           # noqa: E402
from backend.app.transactions import repository as transactions          # noqa: E402

SOURCE = "synthetic-v1"
FOLDER = ROOT / "demo" / "synthetic"


class SeedError(ValueError):
    """The demo files cannot be loaded as they are."""


def prepare(borrowers, tx) -> list:
    """[(borrower row, period_start, period_end, canonical tuples)] from the files as read (every
    column a string). Checks everything before the database is touched."""
    out, errors = [], []
    for b in borrowers.itertuples(index=False):
        if b.synthetic != "true":
            errors.append(f"{b.borrower_id}: not marked synthetic; only synthetic borrowers can be loaded")
            continue
        rows = tx[tx.borrower_id == b.borrower_id]
        try:
            tuples = [(r.transaction_id, dt.date.fromisoformat(r.transaction_date), transactions.money(r.debit_amount),
                       transactions.money(r.credit_amount), transactions.money(r.running_balance),
                       r.transaction_category) for r in rows.itertuples(index=False)]
        except ValueError as e:
            errors.append(f"{b.borrower_id}: {e}")
            continue
        start, end = dt.date.fromisoformat(b.history_start), dt.date.fromisoformat(b.as_of)
        problems = validate(transactions.to_frame(tuples))
        if any(t[4] is None for t in tuples):
            problems.append("rows without a running balance")
        if any(not start <= t[1] < end for t in tuples):
            problems.append(f"rows outside the covered period {start} to {end}")
        errors += [f"{b.borrower_id}: {p}" for p in problems]
        out.append((b, start, end, tuples))
    if errors:
        raise SeedError("; ".join(errors))
    return out


async def seed(maker, prepared) -> dict:
    """Load each prepared borrower that is not in the database yet. Returns {loaded, unchanged,
    differing}, each a list of borrower ids."""
    report = {"loaded": [], "unchanged": [], "differing": []}
    for b, start, end, tuples in prepared:
        async with maker() as session:
            if await session.get(Borrower, b.borrower_id) is not None:
                stored = await transactions.rows(session, b.borrower_id)
                same = transactions.fingerprint(stored) == transactions.fingerprint(tuples)
                report["unchanged" if same else "differing"].append(b.borrower_id)
                continue
            session.add(Borrower(id=b.borrower_id, display_name=b.display_name, synthetic=True))
            await session.flush()
            await transactions.add_batch(session, b.borrower_id, SOURCE, start, end, tuples)
            await session.commit()
            report["loaded"].append(b.borrower_id)
    return report


async def main_async(folder=FOLDER) -> int:
    settings = Settings()
    if settings.database_url is None:
        print("FLOWSCORE_DATABASE_URL is not set")
        return 2
    prepared = prepare(*read(folder))
    engine = make_engine(settings.database_url.get_secret_value())
    try:
        report = await seed(make_sessionmaker(engine), prepared)
    finally:
        await engine.dispose()
    rows = sum(len(p[3]) for p in prepared if p[0].borrower_id in report["loaded"])
    print(f"loaded {len(report['loaded'])} borrowers ({rows} transactions), "
          f"unchanged {len(report['unchanged'])}, differing {len(report['differing'])}")
    for bid in report["differing"]:
        print(f"  {bid}: stored transactions differ from {folder.name}/; not overwritten")
    return 1 if report["differing"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
