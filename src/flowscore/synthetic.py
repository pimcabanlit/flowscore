"""Synthetic Philippine borrowers for the demo (spec docs/specs/02-synthetic-borrowers.md).

DEMO ONLY. Nothing generated here is evidence for any research question (D1, hard rule 9), and
there are no default labels. The generator reproduces the *patterns* of a Philippine savings or
payroll account; every amount comes from a public figure below or is a labelled assumption.
Nothing is read from personal/ or data/, and no amount is taken from anyone's statements (D4).

Public figures (S2-R1). Amounts are drawn around these, per borrower, with a seeded generator:

| Constant | Value | Source |
|---|---|---|
| NCR_MIN_WAGE_DAILY | PHP 695 / day | Wage Order NCR-26, in force from 2025-07-18 (non-agriculture) |
| LFS_DAILY_PAY | 508 / 1,214 / 1,387 | PSA Labor Force Survey, average daily basic pay: service and sales workers (April 2024), professionals and managers (April 2025) |
| WORK_DAYS_5 / WORK_DAYS_6 | 261 / 313 days a year | DOLE factors for monthly pay of 5-day and 6-day workers (daily rate x factor / 12) |
| TAKE_HOME | 0.85 to 0.95 of gross | Employee shares: SSS 5% (2025 schedule), PhilHealth 2.5%, Pag-IBIG PHP 200, plus withholding tax above the minimum wage. Assumption within that range |
| 13th month | one month of basic pay, by 24 December | Presidential Decree 851 |
| OFW_REMITTANCE_6M | PHP 129,000 per OFW over 6 months | PSA 2024 Survey on Overseas Filipinos (average remittance) |
| MERALCO_RATE | PHP 13.0 / kWh | Meralco 2025 overall residential rate, between 12.16 and 13.47 |
| KWH_PER_MONTH | 120 to 250 kWh | Meralco quotes bill changes for a "typical" 200 kWh household |
| INSTAPAY_FEE, PESONET_FEE | PHP 25 and 50 until 2026-06-30, free from 2026-07-01 | Published big-bank fees (BPI, BDO, Metrobank); BPI and BDO waived both fees from July 2026 |
| SAVINGS_RATE | 0.0625% a year, 20% final tax | Typical big-bank regular savings rate; final withholding tax on deposit interest (NIRC sec. 24(B)(1)) |
| LOAD_DENOMINATIONS | PHP 50, 99, 149, 299 | Common prepaid load and promo amounts. Assumption |
| Rent, water, internet, card and loan shares | see draw_profile | Assumptions, stated as shares of take-home pay |

Calendar (S2-R1). Payroll falls on the 15th and the last day of the month. A payday on a
weekend or a fixed-date national holiday moves to the previous working day. Holy Week and the
two Eid holidays move every year and are not modelled; none of them falls on a payday between
2025-10-01 and 2026-09-30.

Account rules (S2-R5). These are savings or payroll accounts, so the balance never goes below
zero (D21: Philippine savings accounts rarely go negative). A cash withdrawal is cut to what
the account holds, in whole PHP 100s, as at an ATM. Any other debit the account cannot cover
(rent, bills, card or loan payment, card purchase, phone load) is skipped, as a declined
payment would be: a load or a purchase is never charged in part.

Money is held in whole centavos internally, so running balances are exact.
"""
from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from flowscore.schema import BALANCE, CATEGORY, CREDIT, DATE, DEBIT, ID, REQUIRED

GENERATOR_VERSION = "synthetic-v1"
DEFAULT_SEED = 2026
HISTORY_START = dt.date(2025, 10, 1)        # 12 full months of history ...
AS_OF = dt.date(2026, 10, 1)                # ... ending the day before the assessment date
PERSONAS = ["steady_salaried", "card_debt", "irregular_freelancer", "remittance_dependent", "near_zero"]
BORROWERS_PER_PERSONA = 6

# public figures (see the table above)
NCR_MIN_WAGE_DAILY = 695.0
LFS_DAILY_PAY = {"service_sales": 508.0, "professionals": 1214.0, "managers": 1387.0}
WORK_DAYS_5, WORK_DAYS_6 = 261, 313
OFW_REMITTANCE_6M = 129_000.0
MERALCO_RATE = 13.0
INSTAPAY_FEE, PESONET_FEE = 25.0, 50.0
FEES_WAIVED_FROM = dt.date(2026, 7, 1)
SAVINGS_RATE, INTEREST_TAX = 0.000625, 0.20
LOAD_DENOMINATIONS = (50, 99, 149, 299)

# fixed-date national holidays (regular and special non-working days), month and day
FIXED_HOLIDAYS = {(1, 1), (4, 9), (5, 1), (6, 12), (8, 21), (11, 1), (11, 30), (12, 8), (12, 24),
                  (12, 25), (12, 30), (12, 31)}

COLUMNS = ["borrower_id"] + REQUIRED
BORROWER_COLUMNS = ["borrower_id", "display_name", "persona", "synthetic", "history_start", "as_of",
                    "generator_version", "seed"]


# ---------------------------------------------------------------------------------------------
# calendar

def holidays(year: int) -> set:
    """Fixed-date national holidays plus National Heroes Day (last Monday of August)."""
    days = {dt.date(year, m, d) for m, d in FIXED_HOLIDAYS}
    last_aug = dt.date(year, 8, 31)
    days.add(last_aug - dt.timedelta(days=last_aug.weekday()))          # weekday 0 = Monday
    return days


def is_working_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in holidays(d.year)


def previous_working_day(d: dt.date) -> dt.date:
    """d itself if it is a working day, else the closest working day before it."""
    while not is_working_day(d):
        d -= dt.timedelta(days=1)
    return d


def paydays(year: int, month: int) -> list:
    """Semi-monthly payroll: the 15th and the last day, each moved back to a working day."""
    last = calendar.monthrange(year, month)[1]
    return [previous_working_day(dt.date(year, month, 15)), previous_working_day(dt.date(year, month, last))]


def months(start: dt.date, end: dt.date) -> list:
    """(year, month) for every calendar month that starts in [start, end)."""
    out, y, m = [], start.year, start.month
    while dt.date(y, m, 1) < end:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def transfer_fee(channel, day: dt.date) -> int:
    """Fee in centavos for an outgoing transfer: InstaPay or PESONet, free from FEES_WAIVED_FROM."""
    if channel is None or day >= FEES_WAIVED_FROM:
        return 0
    return cents({"instapay": INSTAPAY_FEE, "pesonet": PESONET_FEE}[channel])


def cents(pesos: float) -> int:
    return int(round(pesos * 100))


# ---------------------------------------------------------------------------------------------
# borrower profiles

@dataclass(frozen=True)
class Profile:
    """One borrower's parameters. Amounts are PHP per month unless named otherwise.

    The shares (cash_share, card_purchase_share) are of `income_level`. `noise` is the relative
    spread of variable amounts; with noise 0 every fixed amount is exact (used by the tests)."""
    persona: str
    opening_balance: float
    semi_monthly_pay: float = 0.0          # salary credited on each payday
    thirteenth_month: float = 0.0          # extra salary credit on the first December payday
    remittance: float = 0.0                # one transfer_in a month around remittance_day
    remittance_day: int = 5
    extra_remittance_prob: float = 0.0     # chance of a second, smaller remittance in a month
    freelance_mean: float = 0.0            # client payments (transfer_in), irregular
    freelance_zero_prob: float = 0.0       # chance a month has no client payment at all
    side_deposits: float = 0.0             # cash deposits (e.g. a small store), 2-4 a month
    family_support_in_prob: float = 0.0    # chance of a small transfer_in from family in a month
    rent: float = 0.0                      # InstaPay to the landlord, day 5
    electricity: float = 0.0               # bills, day 20
    water: float = 0.0                     # bills, day 22
    internet: float = 0.0                  # bills, day 12
    card_payment: float = 0.0              # credit_card_payment through bills payment, day 23
    loan_payment: float = 0.0              # loan_payment by PESONet, day 10
    family_support_out: float = 0.0        # InstaPay transfer_out, the day after the first payday
    phone_loads: int = 0                   # prepaid load purchases a month
    cash_share: float = 0.0                # ATM withdrawals, 3-5 a month
    card_purchase_share: float = 0.0       # debit card purchases, 3-8 a month
    sweep_after_payday: bool = False       # withdraws nearly everything the day after each payday
    sweep_keep: float = 300.0              # what a sweep leaves in the account
    noise: float = 0.0
    interest: bool = True

    @property
    def income_level(self) -> float:
        return 2 * self.semi_monthly_pay + self.remittance + self.freelance_mean + self.side_deposits


def _take_home_semi_monthly(daily: float, work_days: int, take_home: float) -> float:
    return round(daily * work_days / 12 * take_home / 2, 2)


def draw_profile(persona: str, rng: np.random.Generator) -> Profile:
    """A borrower of the given persona with parameters drawn around the public figures."""
    u = rng.uniform
    if persona == "steady_salaried":
        daily = u(LFS_DAILY_PAY["service_sales"] * 1.6, LFS_DAILY_PAY["managers"])
        semi = _take_home_semi_monthly(daily, WORK_DAYS_5, u(0.85, 0.90))
        pay = 2 * semi
        return Profile(persona, opening_balance=round(pay * u(1.0, 3.0), 2), semi_monthly_pay=semi,
                       thirteenth_month=round(daily * WORK_DAYS_5 / 12, 2),
                       rent=round(pay * u(0.20, 0.28), -2), electricity=MERALCO_RATE * u(120, 220),
                       water=u(300, 600), internet=float(rng.choice([1299, 1699])),
                       card_payment=pay * u(0.08, 0.15), family_support_out=round(pay * u(0.0, 0.08), -2),
                       phone_loads=int(rng.integers(1, 3)), cash_share=u(0.10, 0.18),
                       card_purchase_share=u(0.08, 0.14), noise=0.10)
    if persona == "card_debt":
        daily = u(LFS_DAILY_PAY["service_sales"] * 1.8, LFS_DAILY_PAY["managers"] * 1.1)
        semi = _take_home_semi_monthly(daily, WORK_DAYS_5, u(0.85, 0.90))
        pay = 2 * semi
        return Profile(persona, opening_balance=round(pay * u(0.2, 0.6), 2), semi_monthly_pay=semi,
                       thirteenth_month=round(daily * WORK_DAYS_5 / 12, 2),
                       rent=round(pay * u(0.12, 0.20), -2) if rng.random() < 0.5 else 0.0,
                       electricity=MERALCO_RATE * u(150, 250), water=u(300, 600), internet=1699.0,
                       card_payment=pay * u(0.35, 0.50), loan_payment=round(pay * u(0.10, 0.18), -2),
                       phone_loads=int(rng.integers(2, 5)), cash_share=u(0.10, 0.18),
                       card_purchase_share=u(0.08, 0.15), noise=0.15)
    if persona == "irregular_freelancer":
        mean = LFS_DAILY_PAY["professionals"] * u(0.8, 1.3) * 22
        return Profile(persona, opening_balance=round(mean * u(1.0, 2.5), 2), freelance_mean=mean,
                       freelance_zero_prob=u(0.10, 0.25), rent=round(mean * u(0.15, 0.25), -2),
                       electricity=MERALCO_RATE * u(180, 250), water=u(300, 600), internet=1699.0,
                       card_payment=mean * u(0.05, 0.15), phone_loads=int(rng.integers(2, 5)),
                       cash_share=u(0.15, 0.25), card_purchase_share=u(0.10, 0.20), noise=0.15)
    if persona == "remittance_dependent":
        remit = OFW_REMITTANCE_6M / 6 * u(0.6, 1.4)
        deposits = remit * u(0.10, 0.30) if rng.random() < 0.5 else 0.0
        level = remit + deposits
        return Profile(persona, opening_balance=round(level * u(0.3, 1.0), 2), remittance=remit,
                       remittance_day=int(rng.integers(3, 11)), extra_remittance_prob=0.2,
                       side_deposits=deposits, electricity=MERALCO_RATE * u(120, 200), water=u(250, 500),
                       phone_loads=int(rng.integers(3, 7)), cash_share=u(0.50, 0.70),
                       card_purchase_share=u(0.05, 0.12), noise=0.15)
    if persona == "near_zero":
        semi = _take_home_semi_monthly(NCR_MIN_WAGE_DAILY, WORK_DAYS_6, u(0.92, 0.95))
        return Profile(persona, opening_balance=round(u(200, 800), 2), semi_monthly_pay=semi,
                       thirteenth_month=round(NCR_MIN_WAGE_DAILY * WORK_DAYS_6 / 12, 2),
                       family_support_in_prob=0.25,          # bills are paid in cash, from the sweeps
                       phone_loads=int(rng.integers(3, 7)), sweep_after_payday=True,
                       sweep_keep=round(u(100, 400), -1), noise=0.15)
    raise ValueError(f"unknown persona {persona!r}")


# ---------------------------------------------------------------------------------------------
# simulation

@dataclass(order=True)
class _Event:
    day: dt.date
    order: int                      # 0 credit, 1 debit, 2 month-end interest
    seq: int
    category: str = field(compare=False)
    amount: int = field(compare=False)              # centavos; ignored for sweeps and interest
    divisible: bool = field(compare=False, default=False)    # cash: cut to the balance, not declined
    channel: str = field(compare=False, default=None)
    sweep_keep: int = field(compare=False, default=0)   # > 0: withdraw all but this, to 100s


def _days(rng, year, month, k) -> list:
    last = calendar.monthrange(year, month)[1]
    return sorted(dt.date(year, month, int(d)) for d in rng.integers(1, last + 1, k))


def _split(rng, total: float, k: int) -> np.ndarray:
    return total * rng.dirichlet(np.full(k, 3.0))


def _events(p: Profile, rng: np.random.Generator, start: dt.date, end: dt.date) -> list:
    ev = []

    def add(day, category, amount=0.0, credit=False, **kw):
        if day < start or day >= end:
            return
        ev.append(_Event(day, 0 if credit else 1, len(ev), category, cents(amount), **kw))

    def vary(x):
        return x * max(0.3, 1 + p.noise * rng.standard_normal()) if p.noise else x

    for y, m in months(start, end):
        last = calendar.monthrange(y, m)[1]
        if p.semi_monthly_pay:
            for i, d in enumerate(paydays(y, m)):
                add(d, "salary", p.semi_monthly_pay, credit=True)
                if m == 12 and i == 0 and p.thirteenth_month:
                    add(d, "salary", p.thirteenth_month, credit=True)
                if p.sweep_after_payday:
                    add(d + dt.timedelta(days=1), "cash_withdrawal", divisible=True, sweep_keep=cents(p.sweep_keep))
            if p.family_support_out:
                add(paydays(y, m)[0] + dt.timedelta(days=1), "transfer_out", p.family_support_out,
                    channel="instapay")
        if p.remittance:
            day = int(np.clip(p.remittance_day + rng.integers(-2, 3), 1, 28))
            add(dt.date(y, m, day), "transfer_in", round(vary(p.remittance), 2), credit=True)
            if rng.random() < p.extra_remittance_prob:
                add(_days(rng, y, m, 1)[0], "transfer_in", round(vary(p.remittance * 0.3), -2), credit=True)
        if p.freelance_mean and rng.random() >= p.freelance_zero_prob:
            total = p.freelance_mean * rng.lognormal(-0.18, 0.6)      # mean of lognormal(-s^2/2, s) = 1
            k = int(rng.integers(1, 4))
            for d, a in zip(_days(rng, y, m, k), _split(rng, total, k)):
                add(d, "transfer_in", round(a, 2), credit=True)
        if p.side_deposits:
            k = int(rng.integers(2, 5))
            for d, a in zip(_days(rng, y, m, k), _split(rng, p.side_deposits, k)):
                add(d, "deposit", round(a, -1), credit=True)
        if p.family_support_in_prob and rng.random() < p.family_support_in_prob:
            add(_days(rng, y, m, 1)[0], "transfer_in", float(rng.choice([500, 1000, 1500, 2000])), credit=True)

        if p.rent:
            add(dt.date(y, m, 5), "rent", p.rent, channel="instapay")
        if p.loan_payment:
            add(dt.date(y, m, 10), "loan_payment", p.loan_payment, channel="pesonet")
        if p.internet:
            add(dt.date(y, m, 12), "bills", p.internet)
        if p.electricity:
            add(dt.date(y, m, 20), "bills", round(vary(p.electricity), 2))
        if p.water:
            add(dt.date(y, m, min(22, last)), "bills", round(vary(p.water), 2))
        if p.card_payment:
            add(dt.date(y, m, 23), "credit_card_payment", round(vary(p.card_payment), 2))

        for d in _days(rng, y, m, p.phone_loads):
            add(d, "phone_load", float(rng.choice(LOAD_DENOMINATIONS)))
        if p.cash_share:
            k = int(rng.integers(3, 6))
            for d, a in zip(_days(rng, y, m, k), _split(rng, vary(p.cash_share * p.income_level), k)):
                if round(a, -2) >= 500:
                    add(d, "cash_withdrawal", round(a / 500) * 500.0, divisible=True)
        if p.card_purchase_share:
            k = int(rng.integers(3, 9))
            for d, a in zip(_days(rng, y, m, k), _split(rng, vary(p.card_purchase_share * p.income_level), k)):
                add(d, "card_purchase", round(a, 2))
        if p.interest and start <= dt.date(y, m, last) < end:      # never dated on or after end
            ev.append(_Event(dt.date(y, m, last), 2, len(ev), "interest", 0))
    return sorted(ev)


def simulate(p: Profile, rng: np.random.Generator, borrower_id: str,
             start: dt.date = HISTORY_START, end: dt.date = AS_OF) -> list:
    """Transactions dated in [start, end) for one borrower, as rows of COLUMNS. Amounts are
    strings with two decimals; an absent debit or credit is an empty string, never 0."""
    rows, bal = [], cents(p.opening_balance)

    def post(day, category, amount, credit):
        nonlocal bal
        bal += amount if credit else -amount
        assert bal >= 0, "savings balance went negative"
        rows.append([borrower_id, f"{borrower_id}-{len(rows) + 1:05d}", day.isoformat(),
                     "" if credit else _fmt(amount), _fmt(amount) if credit else "", _fmt(bal), category])

    for e in _events(p, rng, start, end):
        if e.order == 0:
            post(e.day, e.category, e.amount, credit=True)
            continue
        if e.order == 2:                       # month-end interest, net of final tax
            amount = int(bal * SAVINGS_RATE / 12 * (1 - INTEREST_TAX))
            if amount > 0:
                post(e.day, "interest", amount, credit=True)
            continue
        fee = transfer_fee(e.channel, e.day)
        amount = e.amount
        if e.sweep_keep:
            amount = (bal - e.sweep_keep) // 10_000 * 10_000
        elif amount + fee > bal and e.divisible:
            amount = (bal - fee) // 10_000 * 10_000
        if amount <= 0 or amount + fee > bal:
            continue                            # cannot be covered: declined, or no cash left
        post(e.day, e.category, amount, credit=False)
        if fee:
            post(e.day, "fee", fee, credit=False)
    return rows


def _fmt(c: int) -> str:
    return f"{c // 100}.{c % 100:02d}"


# ---------------------------------------------------------------------------------------------
# the borrower set

def generate(seed: int = DEFAULT_SEED) -> tuple:
    """(borrowers, transactions) as DataFrames of strings, ready to write. Each borrower has its
    own random stream, seeded by (seed, index), so one borrower never shifts another."""
    borrowers, rows = [], []
    for pi, persona in enumerate(PERSONAS):
        for j in range(BORROWERS_PER_PERSONA):
            n = pi * BORROWERS_PER_PERSONA + j + 1
            bid = f"SYN-{n:03d}"
            rng = np.random.default_rng([seed, n])
            rows += simulate(draw_profile(persona, rng), rng, bid)
            borrowers.append([bid, f"Demo Borrower {n:02d}", persona, "true", HISTORY_START.isoformat(),
                              AS_OF.isoformat(), GENERATOR_VERSION, str(seed)])
    return (pd.DataFrame(borrowers, columns=BORROWER_COLUMNS), pd.DataFrame(rows, columns=COLUMNS))


def write(out_dir, seed: int = DEFAULT_SEED) -> tuple:
    """Write borrowers.csv and transactions.csv to out_dir. LF line endings, so the bytes are the
    same on every platform."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    borrowers, tx = generate(seed)
    paths = (out / "borrowers.csv", out / "transactions.csv")
    for df, path in zip((borrowers, tx), paths):
        df.to_csv(path, index=False, lineterminator="\n")
    return paths


def to_canonical(tx: pd.DataFrame) -> pd.DataFrame:
    """One borrower's rows (as written) -> the canonical schema: datetime dates, float amounts,
    NaN where a debit or credit is absent."""
    df = tx[REQUIRED].copy()
    df[DATE] = pd.to_datetime(df[DATE])
    for c in (DEBIT, CREDIT, BALANCE):
        df[c] = pd.to_numeric(df[c].replace("", np.nan)).astype(float)
    df[ID], df[CATEGORY] = df[ID].astype(str), df[CATEGORY].astype(str)
    return df


def read(out_dir) -> tuple:
    """(borrowers, transactions) as written, every column a string ('' for an empty cell)."""
    out = Path(out_dir)
    load = lambda f: pd.read_csv(out / f, dtype=str, keep_default_na=False)
    return load("borrowers.csv"), load("transactions.csv")


__all__ = ["Profile", "draw_profile", "simulate", "generate", "write", "read", "to_canonical", "paydays",
           "previous_working_day", "holidays", "transfer_fee"]
