from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pytest
from bpi_parser import parse_pdf, build_transactions, categorize

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.mark.parametrize("style", ["lines", "rects", "none"])   # drawn lines, box borders, no borders
def test_fake_statement_parses_cleanly(style):
    pdf = FIXTURES / f"fake_bpi_{style}.pdf"
    rows, period, pages = parse_pdf(pdf)
    tx, opening, issues = build_transactions(rows, period, pdf.name)
    assert opening == 10000.00 and issues == [] and len(tx) == 11
    assert str(tx[0]["transaction_date"].date()) == "2025-12-15"      # Dec -> start year
    assert str(tx[6]["transaction_date"].date()) == "2026-01-02"      # Jan -> end year
    assert "WRAPPED DETAIL LINE" in tx[3]["details"]                   # continuation joined
    assert tx[2]["debit_amount"] == 450.50 and tx[0]["credit_amount"] == 30000.00

def test_balance_mismatch_is_flagged():
    rows = [dict(date="", description="BEGINNING BALANCE", ref="", details="", debit="", credit="", balance="100.00", page=1, top=100),
            dict(date="Jan 05", description="Payroll", ref="", details="", debit="", credit="50.00", balance="999.00", page=1, top=112)]
    _, _, issues = build_transactions(rows, (1, 2026, 3, 2026), "x.pdf")
    assert len(issues) == 1 and "mismatch" in issues[0]

def test_categories():
    assert categorize("Bizlink Payroll", "BIZLINK", True) == "salary"
    assert categorize("Bills Payment", "TO: BPI CREDIT CARD.....X", False) == "credit_card_payment"
    assert categorize("Purchase-MC @fp*Food", "", False) == "card_purchase"
    assert categorize("Instapay Transfer", "FROM JUAN", True) == "transfer_in"
    assert categorize("Something odd", "", False) == "other_out"

def test_multipage_wide_letter_spacing():
    """Words split into single letters, summary page first, 3 table pages: every page and row must be read."""
    pdf = FIXTURES / "fake_bpi_wide.pdf"
    rows, period, pages = parse_pdf(pdf)
    tx, opening, issues = build_transactions(rows, period, pdf.name)
    assert [p[1] for p in pages if p[0] > 0] == ["skipped (no table header)", "read", "read", "read"]
    assert len(tx) == 110 and opening == 15000.00 and issues == []
