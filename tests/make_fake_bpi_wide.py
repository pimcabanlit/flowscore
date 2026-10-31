"""FAKE multi-page BPI-style statement: summary page, thick box borders, very wide letter spacing. All data invented."""
import sys, random
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import make_fake_bpi as m
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
random.seed(1)
m.COLS = [30, 75, 280, 320, 545, 650, 755, 865]
W, H = A4[1], A4[0]
c = canvas.Canvas(sys.argv[1], pagesize=(W, H))
m.spaced(c, 90, H-60, "ACCOUNT SUMMARY FOR THE PERIOD JUL 14, 2026 - OCT 14, 2026", size=10, cs=3)
for i, t in enumerate(["Beginning Balance", "Plus: Total Credits", "from EOL / Mobile Transactions", "Less: Total Debits", "Ending Balance"]):
    m.spaced(c, 100, H-100-20*i, t, size=8, cs=2)
c.showPage()
descs = [("Bizlink Payroll","708","BIZLINK","c"),("Bills Payment","0010","TO: BPI CREDIT CARD.....XXXXX0000","d"),
         ("Purchase-MC @fp*Food","000","","d"),("Purchase-MC @GRAB","000","","d"),("InstaPay Transfer","","TRANSFER TO OTHER BANK","d"),
         ("ATM Withdrawal Fee-BDO@0020121","291","","d"),("ATM Withdrawal-BDO@00201213","291","","d"),
         ("Fund Transfer","120","FROM:JUAN DELA CRUZ","c"),("Prepaid Phone Reload","9550","TO: PREPAID PHONE R.....XXXXX0000","d"),
         ("Payment to Merchant","","PAYMENT TO MERCHANT","d")]
bal = 15000.00; day = 15; month = ["Jul","Aug","Sep","Oct"]; mi = 0
rows = [("", "BEGINNING BALANCE", "", "", "", "", f"{bal:,.2f}")]
for k in range(110):
    d, ref, det, side = random.choice(descs)
    amt = round(random.uniform(50, 30000 if side == "c" else 3000), 2)
    bal = bal + amt if side == "c" else bal - amt
    day += random.choice([0, 0, 1]);
    if day > 28: day, mi = 1, min(mi+1, 3)
    rows.append((f"{month[mi]} {day:02d}", d, ref, det, f"{amt:,.2f}" if side=="d" else "", f"{amt:,.2f}" if side=="c" else "", f"{bal:,.2f}"))
per = 40
for p in range(0, len(rows), per):
    m.spaced(c, 40, H-50, "PERIOD COVERED JUL 14, 2026 - OCT 14, 2026", size=7, cs=1.5)
    top = H-70
    for x in m.COLS: c.rect(x-1.3, 40, 2.6, top-40, stroke=0, fill=1)      # thick filled borders
    c.rect(m.COLS[0], top-2, m.COLS[-1]-m.COLS[0], 2.6, stroke=0, fill=1); c.rect(m.COLS[0], top-34, m.COLS[-1]-m.COLS[0], 2.6, stroke=0, fill=1)
    for i, h in enumerate(m.HEAD): m.spaced(c, (m.COLS[i]+m.COLS[i+1])/2, top-21, h, size=7, cs=3.5, anchor="center")
    y = top - 55
    for r in rows[p:p+per]:
        date, desc, ref, det, deb, cre, b = r
        m.spaced(c, m.COLS[0]+5, y, date, size=6.5, cs=3.5); m.spaced(c, m.COLS[1]+5, y, desc, size=6.5, cs=3.5)
        m.spaced(c, m.COLS[2]+5, y, ref, size=6.5, cs=3.5); m.spaced(c, m.COLS[3]+5, y, det, size=6.5, cs=3.5)
        if deb: m.spaced(c, m.COLS[5]-8, y, deb, size=6.5, cs=3.5, anchor="right")
        if cre: m.spaced(c, m.COLS[6]-8, y, cre, size=6.5, cs=3.5, anchor="right")
        m.spaced(c, m.COLS[7]-8, y, b, size=6.5, cs=3.5, anchor="right")
        y -= 11
    c.showPage()
c.save()
