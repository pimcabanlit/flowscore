"""BPI statement PDF -> transaction CSV in the FlowScore schema. LOCAL USE ONLY.

Usage (Windows PowerShell or any shell):
    python tools/bpi_parser.py personal/statements -o personal/transactions.csv
    python tools/bpi_parser.py one.pdf two.pdf -o out.csv

Reads every transaction page (Date | Description | Ref | Details | Debit | Credit | Balance),
takes the year from "PERIOD COVERED", joins wrapped lines, checks every running balance,
removes duplicates where statements overlap, and adds a rule-based category.
"""
import argparse
import io
import logging
import re
import sys
from pathlib import Path

import pandas as pd
import pdfplumber

logging.getLogger("pdfminer").setLevel(logging.ERROR)

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}
HEADERS = ["DATE", "DESCRIPTION", "REF", "DETAILS", "DEBIT", "CREDIT", "BALANCE"]
FIELDS = ["date", "description", "ref", "details", "debit", "credit", "balance"]
PERIOD_RE = re.compile(r"PERIODCOVERED([A-Z]{3})(\d{1,2}),(\d{4})-([A-Z]{3})(\d{1,2}),(\d{4})")
DATE_RE = re.compile(r"^([A-Za-z]{3})(\d{1,2})$")
AMOUNT_RE = re.compile(r"^-?[\d,]+\.\d{2}$")

# ---------- categories: first matching rule wins (text = description + details, upper case, no spaces)
RULES = [
    ("salary",              "credit", ["PAYROLL", "SALARY"]),
    ("interest",            "credit", ["INTEREST"]),
    ("tax",                 "debit",  ["TAXWITHHELD", "WITHHOLDING"]),
    ("credit_card_payment", "debit",  ["CREDITCARD"]),
    ("loan_payment",        "debit",  ["LOAN"]),
    ("bills",               "debit",  ["BILLSPAYMENT", "BILLSPAY"]),
    ("fee",                 "debit",  ["SERVICECHARGE", "FEE"]),          # before ATM: "ATM Withdrawal Fee"
    ("phone_load",          "debit",  ["PREPAIDPHONE", "RELOAD", "LOAD"]),
    ("card_purchase",       "debit",  ["PURCHASE", "POS", "PAYMENTTOMERCHANT"]),
    ("cash_withdrawal",     "debit",  ["ATM", "WITHDRAWAL"]),
    ("deposit",             "credit", ["DEPOSIT"]),
    ("transfer_in",         "credit", ["INSTAPAY", "PESONET", "TRANSFER", "GCASH", "MAYA"]),
    ("transfer_out",        "debit",  ["INSTAPAY", "PESONET", "TRANSFER", "GCASH", "MAYA"]),
]


def categorize(description: str, details: str, is_credit: bool) -> str:
    text = re.sub(r"\s+", "", f"{description}{details}").upper()
    side = "credit" if is_credit else "debit"
    for name, rule_side, keys in RULES:
        if rule_side == side and any(k in text for k in keys):
            return name
    return "other_in" if is_credit else "other_out"


def to_amount(s: str):
    s = re.sub(r"\s+", "", s or "")
    return float(s.replace(",", "")) if AMOUNT_RE.match(s) else None


def _lines(chars, tol=2.0):
    """Group characters into visual lines by their vertical position."""
    out = []
    for c in sorted(chars, key=lambda c: (c["top"], c["x0"])):
        if out and abs(c["top"] - out[-1][0]) <= tol:
            out[-1][1].append(c)
        else:
            out.append([c["top"], [c]])
    return [(top, sorted(cs, key=lambda c: c["x0"])) for top, cs in out]


def _text(chars):
    """Join characters; keep real spaces, and add one where a gap is much wider than the letter spacing."""
    solid = [c for c in chars if c["text"].strip()]
    if not solid:
        return ""
    gaps = sorted(b["x0"] - a["x1"] for a, b in zip(solid, solid[1:]))
    typical = gaps[len(gaps) // 2] if gaps else 0
    out, prev = [], None
    for c in chars:
        if not c["text"].strip():
            out.append(" "); continue
        if prev is not None and c["x0"] - prev["x1"] > max(2.5 * typical, typical + 2.5):
            out.append(" ")
        out.append(c["text"]); prev = c
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _header(lines):
    """Find the header line by its letters alone, whatever the spacing. Returns phrase x-ranges + bottom."""
    for top, cs in lines:
        solid = [c for c in cs if c["text"].strip()]
        s = "".join(c["text"] for c in solid).upper()
        pos, at = [], 0
        for h in HEADERS:
            i = s.find(h, at)
            if i < 0:
                break
            pos.append(i); at = i + len(h)
        if len(pos) != len(HEADERS):
            continue
        phrases = []
        for k, i in enumerate(pos):
            j = (pos[k + 1] if k + 1 < len(pos) else len(solid)) - 1      # phrase ends before next anchor
            phrases.append([solid[i]["x0"], solid[j]["x1"]])
        return phrases, max(c["bottom"] for c in solid)
    return None, None


def _column_edges(page, phrases, header_bottom, chars, debug=False):
    """Border between each pair of header phrases: a drawn line/box edge, else the widest empty strip, else the middle."""
    by_x = {}
    for e in page.vertical_edges:
        if e["bottom"] > header_bottom:
            k = round(e["x0"])
            by_x[k] = by_x.get(k, 0) + abs(e["bottom"] - e["top"])
    verticals = sorted(x for x, length in by_x.items() if length > 40)
    data = [c for c in chars if c["top"] > header_bottom and c["text"].strip()]
    edges, how = [-1e9], []
    for (l0, l1), (r0, r1) in zip(phrases, phrases[1:]):
        lo, hi = l1, r0
        cands = [x for x in verticals if lo - 1 <= x <= hi + 1]
        if cands:
            mid = (lo + hi) / 2
            edges.append(min(cands, key=lambda x: abs(x - mid))); how.append("line"); continue
        covered = [False] * max(1, int(hi - lo) + 1)
        for c in data:
            for x in range(max(0, int(c["x0"] - lo)), min(len(covered), int(c["x1"] - lo) + 1)):
                covered[x] = True
        best, run = None, None
        for i, cv in enumerate(covered + [True]):
            if not cv and run is None:
                run = i
            elif cv and run is not None:
                if best is None or i - run > best[1] - best[0]:
                    best = (run, i)
                run = None
        if best:
            edges.append(lo + (best[0] + best[1]) / 2); how.append("gap")
        else:
            edges.append((lo + hi) / 2); how.append("middle")
    edges.append(1e9)
    if debug:
        print(f"    header phrases x: {[(round(a), round(b)) for a, b in phrases]}")
        print(f"    vertical edges x: {verticals}")
        print(f"    column borders:   {[round(e) for e in edges[1:-1]]}  via {how}")
    return edges


def _mask(text):
    return re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", text))


def open_pdf(path: Path):
    """Open a PDF for pdfplumber, rebuilt by qpdf (pikepdf) first.

    Some bank PDFs have a damaged page index: viewers repair it silently, but pdfplumber then
    sees only some of the pages. Rebuilding the file in memory fixes that. Returns (pdf, note).
    """
    try:
        import pikepdf
    except ImportError:
        return pdfplumber.open(path), "pikepdf not installed: no repair"
    buf = io.BytesIO()
    with pikepdf.open(path) as src:
        expected = len(src.pages)
        src.save(buf)
    buf.seek(0)
    pdf = pdfplumber.open(buf)
    note = None
    if len(pdf.pages) != expected:
        note = f"WARNING: qpdf sees {expected} pages but pdfplumber reads {len(pdf.pages)}"
    return pdf, note


def parse_pdf(path: Path, debug=False):
    """Returns (rows, period, page_report). Each row = raw cell text per column + page + vertical position."""
    rows, period, edges, report = [], None, None, []
    pdf, note = open_pdf(path)
    if note:
        report.append((0, note, 0))
    with pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = re.sub(r"\s+", "", (page.extract_text() or "")).upper()
            m = PERIOD_RE.search(text)
            if m:
                period = (MONTHS[m[1]], int(m[3]), MONTHS[m[4]], int(m[6]))
            chars = page.chars
            lines = _lines(chars)
            if debug:
                print(f"  page {pno}:")
            phrases, header_bottom = _header(lines)
            if phrases is not None:
                edges = _column_edges(page, phrases, header_bottom, chars, debug)
                status = "read"
            elif edges is not None:
                header_bottom = -1e9                     # continuation page: reuse the last borders
                status = "read (no header, previous columns)"
            else:
                report.append((pno, "skipped (no table header)", 0)); continue
            n_dated = 0
            for top, cs in lines:
                if top <= header_bottom:
                    continue
                cells = {f: [] for f in FIELDS}
                for c in cs:
                    cx = (c["x0"] + c["x1"]) / 2
                    col = next(i for i in range(len(FIELDS)) if edges[i] <= cx < edges[i + 1])
                    cells[FIELDS[col]].append(c)
                cells = {k: _text(v) for k, v in cells.items()}
                if not any(cells.values()):
                    continue
                if DATE_RE.match(re.sub(r"\s+", "", cells["date"])):
                    n_dated += 1
                if debug and n_dated <= 4 and any(cells.values()):
                    print("    row:", {k: _mask(v) for k, v in cells.items() if v})
                cells.update(page=pno, top=top, file=path.name)
                rows.append(cells)
            report.append((pno, status, n_dated))
    if period is None:
        raise ValueError(f"{path.name}: no 'PERIOD COVERED' line found")
    return rows, period, report


def build_transactions(rows, period, source):
    start_m, start_y, end_m, end_y = period
    out, opening, issues = [], None, []
    for r in rows:
        desc_u = re.sub(r"\s+", "", r["description"]).upper()
        if "BEGINNINGBALANCE" in desc_u or "BALANCEFORWARD" in desc_u:
            opening = to_amount(r["balance"]); continue
        if "ENDINGBALANCE" in desc_u:
            continue
        dm = DATE_RE.match(re.sub(r"\s+", "", r["date"]))
        if dm and dm[1].upper() in MONTHS:
            month = MONTHS[dm[1].upper()]
            year = start_y if (start_y == end_y or month >= start_m) else end_y
            out.append(dict(transaction_date=pd.Timestamp(year, month, int(dm[2])),
                            description=r["description"], ref=r["ref"], details=r["details"],
                            debit_amount=to_amount(r["debit"]), credit_amount=to_amount(r["credit"]),
                            running_balance=to_amount(r["balance"]), source_file=source, page=r["page"],
                            _top=r["top"]))
        elif out and not r["date"] and (r["details"] or r["description"]) and not any(
                to_amount(r[k]) for k in ("debit", "credit", "balance")) and \
                out[-1]["page"] == r["page"] and 0 < r["top"] - out[-1]["_top"] < 15:
            prev = out[-1]                                   # wrapped continuation line
            prev["_top"] = r["top"]
            prev["details"] = f"{prev['details']} {r['details']}".strip()
            if r["description"]:
                prev["description"] = f"{prev['description']} {r['description']}".strip()
    # running-balance check: previous balance - debit + credit = balance
    bal = opening
    for t in out:
        d, c = t["debit_amount"] or 0.0, t["credit_amount"] or 0.0
        if d and c:
            issues.append(f"{source} {t['transaction_date'].date()} '{t['description']}': both debit and credit")
        if bal is not None and t["running_balance"] is not None and abs(bal - d + c - t["running_balance"]) > 0.005:
            issues.append(f"{source} {t['transaction_date'].date()} '{t['description']}': "
                          f"balance mismatch (expected {bal - d + c:,.2f}, statement says {t['running_balance']:,.2f})")
        bal = t["running_balance"] if t["running_balance"] is not None else (None if bal is None else bal - d + c)
    return out, opening, issues


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="PDF files or folders of PDFs")
    ap.add_argument("-o", "--out", required=True, help="output CSV path")
    ap.add_argument("--debug", action="store_true",
                    help="print column geometry and masked rows (letters->a, digits->9); safe to share")
    args = ap.parse_args(argv)

    pdfs, seen = [], set()
    for p in map(Path, args.inputs):
        for f in (sorted(p.iterdir()) if p.is_dir() else [p]):
            key = str(f.resolve()).lower()
            if f.suffix.lower() == ".pdf" and key not in seen:
                seen.add(key); pdfs.append(f)
    if not pdfs:
        sys.exit("No PDFs found.")

    all_tx, all_issues, summary = [], [], []
    for pdf in pdfs:
        try:
            if args.debug:
                print(f"{pdf.name}")
            rows, period, pages = parse_pdf(pdf, args.debug)
        except Exception as e:                               # keep going, report at the end
            all_issues.append(f"{pdf.name}: could not parse ({e})"); continue
        tx, opening, issues = build_transactions(rows, period, pdf.name)
        all_tx += tx; all_issues += issues
        summary.append((pdf.name, len(tx), opening, pages))

    df = pd.DataFrame(all_tx)
    if df.empty:
        sys.exit("No transactions found. " + " | ".join(all_issues))
    before = len(df)
    df = df.drop_duplicates(subset=["transaction_date", "description", "ref", "details",
                                    "debit_amount", "credit_amount", "running_balance"])
    df = df.sort_values(["transaction_date", "source_file", "page"], kind="stable").reset_index(drop=True)
    df["transaction_id"] = [f"T{i:06d}" for i in range(1, len(df) + 1)]
    df["transaction_category"] = [categorize(r.description, r.details, (r.credit_amount or 0) > 0)
                                  for r in df.itertuples()]
    cols = ["transaction_id", "transaction_date", "description", "ref", "details", "debit_amount",
            "credit_amount", "running_balance", "transaction_category", "source_file"]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df[cols].to_csv(args.out, index=False)

    print(f"Parsed {len(pdfs)} PDF(s) -> {len(df)} transactions "
          f"({before - len(df)} duplicates removed), "
          f"{df.transaction_date.min().date()} to {df.transaction_date.max().date()}")
    for name, n, opening, pages in summary:
        print(f"  {name}: {n} rows, opening balance {'found' if opening is not None else 'MISSING'}, "
              f"{sum(p[0] > 0 for p in pages)} pages")
        for pno, status, n_dated in pages:
            if pno == 0:
                print(f"      {status}"); continue
            print(f"      page {pno}: {status}" + (f", {n_dated} dated rows" if status.startswith("read") else ""))
    print("\nCategories:")
    print(df.transaction_category.value_counts().to_string())
    print(f"\nChecks: {len(all_issues)} issue(s)")
    for i in all_issues[:30]:
        print("  -", i)
    if len(all_issues) > 30:
        print(f"  ... and {len(all_issues) - 30} more")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
