"""Generate a FAKE BPI-style statement PDF for testing the parser. All data invented."""
import sys
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

COLS = [40, 110, 330, 380, 600, 700, 800, 900]          # vertical table lines (x)
HEAD = ["DATE", "DESCRIPTION", "REF", "DETAILS", "DEBIT AMOUNT", "CREDIT AMOUNT", "BALANCE"]

def spaced(c, x, y, text, size=7, cs=1.2, anchor="left"):
    t = c.beginText(); t.setFont("Helvetica", size); t.setCharSpace(cs)
    w = c.stringWidth(text, "Helvetica", size) + cs * len(text)
    if anchor == "right": x -= w
    if anchor == "center": x -= w / 2
    t.setTextOrigin(x, y); t.textOut(text); c.drawText(t)

def table_frame(c, top, bottom, style):
    if style == "lines":
        c.rect(COLS[0], bottom, COLS[-1] - COLS[0], top - bottom)
        for x in COLS[1:-1]: c.line(x, bottom, x, top)
        c.line(COLS[0], top - 30, COLS[-1], top - 30)
    elif style == "rects":                       # every cell border drawn as thin filled boxes
        for x in COLS: c.rect(x - 0.4, bottom, 0.8, top - bottom, stroke=0, fill=1)
    for i, h in enumerate(HEAD): spaced(c, (COLS[i] + COLS[i+1]) / 2, top - 19, h, anchor="center")

def row(c, y, r):
    date, desc, ref, det, deb, cre, bal = r
    spaced(c, COLS[0] + 6, y, date); spaced(c, COLS[1] + 6, y, desc); spaced(c, COLS[2] + 6, y, ref)
    spaced(c, COLS[3] + 6, y, det)
    if deb: spaced(c, COLS[5] - 8, y, deb, anchor="right")
    if cre: spaced(c, COLS[6] - 8, y, cre, anchor="right")
    if bal: spaced(c, COLS[7] - 8, y, bal, anchor="right")

def main(path, style="lines"):
    c = canvas.Canvas(path, pagesize=landscape(A4)); W, H = landscape(A4)
    # page 1: summary with heavily letter-spaced text (parser must ignore)
    spaced(c, 60, H - 80, "ACCOUNT SUMMARY FOR THE PERIOD DEC 14, 2025 - MAR 14, 2026", size=10, cs=4)
    spaced(c, 60, H - 120, "Beginning Balance", size=8, cs=2); spaced(c, 60, H - 140, "Plus: Total Credits", size=8, cs=2)
    c.showPage()
    pages = [
        [("", "BEGINNING BALANCE", "", "", "", "", "10,000.00"),
         ("Dec 15", "Acme Payroll", "708", "ACME CORP", "", "30,000.00", "40,000.00"),
         ("Dec 15", "Bills Payment", "0010", "TO: BPI CREDIT CARD.....XXXXX0000", "12,500.00", "", "27,500.00"),
         ("Dec 20", "Purchase-MC @fp*Food", "000", "", "450.50", "", "27,049.50"),
         ("Dec 28", "Instapay Transfer", "411", "TO: GCASH 0917XXXXXXX", "2,000.00", "", "25,049.50"),
         ("", "", "", "REF 99887766 WRAPPED DETAIL LINE", "", "", ""),
         ("Dec 31", "Interest Earned", "", "", "", "3.21", "25,052.71"),
         ("Dec 31", "Tax Withheld", "", "", "0.64", "", "25,052.07")],
        [("Jan 02", "ATM Withdrawal", "123", "BPI ATM MAKATI", "5,000.00", "", "20,052.07"),
         ("Jan 15", "Acme Payroll", "708", "ACME CORP", "", "30,000.00", "50,052.07"),
         ("Jan 16", "Bills Payment", "0010", "TO: MERALCO", "3,100.00", "", "46,952.07"),
         ("Feb 15", "Acme Payroll", "708", "ACME CORP", "", "30,000.00", "76,952.07"),
         ("Mar 10", "Fund Transfer", "222", "TO: SAVINGS XXXX1111", "40,000.00", "", "36,952.07")],
    ]
    for n, rows in enumerate(pages, start=2):
        spaced(c, W - 80, H - 30, f"Page {n} of 3", size=7)
        spaced(c, 40, H - 50, "PERIOD COVERED DEC 14, 2025 - MAR 14, 2026", size=7, cs=1.5)
        spaced(c, W - 160, H - 50, "NO: 0000-0000-00", size=7)
        top = H - 60; table_frame(c, top, 60, style)
        y = top - 50
        for r in rows: row(c, y, r); y -= 13
        c.showPage()
    c.save()

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "lines")
