"""Keeps the status tables in docs/specs/ honest (see "Status tracking" in docs/specs/README.md).

Rules:
1. Every requirement a spec defines (**S1-R5.) has exactly one row in its Status table, and no row
   names a requirement the spec does not define.
2. Status is planned, implemented or dropped.
3. implemented needs a date (YYYY-MM-DD, not in the future), a PR (#12) and evidence (the test or
   check that proves it). dropped needs a date and a reason in Evidence.
4. A test that cites a requirement id (S1-R5) means that requirement is implemented: the spec must
   say so. This is what makes the status update part of the same PR as the code.
"""
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "docs" / "specs"
TESTS = ROOT / "tests"

DEFINED = re.compile(r"\*\*(S\d+-R\d+)\.")
ROW = re.compile(r"^\|\s*(S\d+-R\d+)\s*\|(.*)\|\s*$", re.M)
CITED = re.compile(r"\bS\d+-R\d+\b")
STATUSES = {"planned", "implemented", "dropped"}


def parse_rows(text: str) -> list:
    """(id, status, date, pr, evidence) for each row of the Status table."""
    rows = []
    for m in ROW.finditer(text):
        cells = [c.strip() for c in m.group(2).split("|")]
        cells += [""] * (4 - len(cells))
        rows.append((m.group(1), *cells[:4]))
    return rows


def check_spec(name: str, text: str, today: dt.date) -> list:
    errors = []
    defined = DEFINED.findall(text)
    rows = parse_rows(text)
    ids = [r[0] for r in rows]
    for i in sorted(set(defined) - set(ids)):
        errors.append(f"{name}: {i} has no row in the Status table")
    for i in sorted(set(ids) - set(defined)):
        errors.append(f"{name}: Status row {i} is not a requirement in this spec")
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"{name}: {i} has more than one Status row")
    for i, status, date, pr, evidence in rows:
        if status not in STATUSES:
            errors.append(f"{name}: {i} status '{status}' is not one of {sorted(STATUSES)}")
            continue
        if status == "planned":
            continue
        try:
            d = dt.date.fromisoformat(date)
            if d > today:
                errors.append(f"{name}: {i} date {date} is in the future")
        except ValueError:
            errors.append(f"{name}: {i} is {status} but date '{date}' is not YYYY-MM-DD")
        if status == "implemented" and not re.fullmatch(r"#\d+", pr):
            errors.append(f"{name}: {i} is implemented but PR '{pr}' is not like #12")
        if not evidence:
            errors.append(f"{name}: {i} is {status} but Evidence is empty "
                          f"({'the test or check that proves it' if status == 'implemented' else 'the reason'})")
    return errors


def check_citations(statuses: dict, cited: dict) -> list:
    """statuses: id -> status. cited: id -> files whose tests cite it."""
    errors = []
    for i, files in sorted(cited.items()):
        where = ", ".join(sorted(files))
        if i not in statuses:
            errors.append(f"{where} cites {i}, which no spec defines")
        elif statuses[i] != "implemented":
            errors.append(f"{where} cites {i} but its spec says '{statuses[i]}': set it to implemented "
                          f"with today's date, the PR number and the test as evidence")
    return errors


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)   # allow any time zone


def test_spec_status_tables_are_valid():
    errors = []
    for p in sorted(SPECS.glob("[0-9]*.md")):
        errors += check_spec(p.name, p.read_text(encoding="utf-8"), _today())
    assert not errors, "\n".join(errors)


def test_cited_requirements_are_marked_implemented():
    statuses = {}
    for p in sorted(SPECS.glob("[0-9]*.md")):
        statuses.update({r[0]: r[1] for r in parse_rows(p.read_text(encoding="utf-8"))})
    cited = {}
    for p in sorted(TESTS.rglob("test_*.py")):
        if p.name == Path(__file__).name:
            continue
        for i in set(CITED.findall(p.read_text(encoding="utf-8"))):
            cited.setdefault(i, set()).add(p.name)
    errors = check_citations(statuses, cited)
    assert not errors, "\n".join(errors)


# The checker itself, on made-up tables -------------------------------------------------------

SPEC = """**S9-R1. One.** text
**S9-R2. Two.** text

| Req | Status | Date | PR | Evidence |
|---|---|---|---|---|
| S9-R1 | {s1} |
| S9-R2 | planned | | | |
"""
TODAY = dt.date(2026, 11, 3)


def test_checker_accepts_valid_rows():
    good = SPEC.format(s1="implemented | 2026-11-03 | #12 | tests/test_api.py")
    assert check_spec("x", good, TODAY) == []
    dropped = SPEC.format(s1="dropped | 2026-11-01 | | replaced by S9-R2")
    assert check_spec("x", dropped, TODAY) == []


def test_checker_rejects_bad_rows():
    assert check_spec("x", SPEC.format(s1="done | 2026-11-03 | #12 | t"), TODAY) == [
        "x: S9-R1 status 'done' is not one of ['dropped', 'implemented', 'planned']"]
    assert check_spec("x", SPEC.format(s1="implemented | 2026-11-04 | #12 | t"), TODAY) == [
        "x: S9-R1 date 2026-11-04 is in the future"]
    assert check_spec("x", SPEC.format(s1="implemented | 3 Nov | 12 | "), TODAY) == [
        "x: S9-R1 is implemented but date '3 Nov' is not YYYY-MM-DD",
        "x: S9-R1 is implemented but PR '12' is not like #12",
        "x: S9-R1 is implemented but Evidence is empty (the test or check that proves it)"]
    missing_row = SPEC.replace("| S9-R2 | planned | | | |\n", "| S9-R3 | planned | | | |\n").format(s1="planned")
    assert check_spec("x", missing_row, TODAY) == [
        "x: S9-R2 has no row in the Status table", "x: Status row S9-R3 is not a requirement in this spec"]


def test_citation_check():
    statuses = {"S9-R1": "implemented", "S9-R2": "planned"}
    assert check_citations(statuses, {"S9-R1": {"test_a.py"}}) == []
    assert check_citations(statuses, {"S9-R2": {"test_a.py"}, "S9-R7": {"test_b.py"}}) == [
        "test_a.py cites S9-R2 but its spec says 'planned': set it to implemented "
        "with today's date, the PR number and the test as evidence",
        "test_b.py cites S9-R7, which no spec defines"]
