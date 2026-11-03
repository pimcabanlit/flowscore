/**
 * Writing API figures as text. Formatting only: no figure is derived here (S4-R2). Band words
 * are always relative to the Berka reference borrowers (S4-R8, D22).
 */
import type { Band, Unit } from "./api";

export const BAND_LABEL: Record<Band, string> = {
  lower: "Lower relative risk",
  middle: "Middle relative risk",
  higher: "Higher relative risk",
};

const money = new Intl.NumberFormat("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const moneyShort = new Intl.NumberFormat("en-PH", { notation: "compact", maximumFractionDigits: 1 });

/** An amount, or an em dash for an unknown one (never 0: hard rule 6). */
export function formatMoney(v: number | null): string {
  return v === null ? "—" : money.format(v);
}

export function formatMoneyShort(v: number): string {
  return moneyShort.format(v);
}

export function formatPercentile(p: number): string {
  return p.toFixed(1);
}

const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
const monthShort = new Intl.DateTimeFormat("en-GB", { month: "short", timeZone: "UTC" });

/** "2026-10-01" -> "1 Oct 2026". Dates from the API are calendar dates, read as UTC. */
export function formatDate(iso: string): string {
  return day.format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));
}

/** The day before an exclusive end date, for "1 Jul 2026 to 30 Sep 2026". Calendar arithmetic
 * on a date label, not on a figure. */
export function formatDayBefore(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return day.format(d);
}

/** "2026-09" -> "Sep 2026" (long) or "Sep" (short). */
export function formatMonth(ym: string, short = false): string {
  const d = new Date(`${ym}-01T00:00:00Z`);
  return (short ? monthShort : monthFmt).format(d);
}

/** A feature's raw value in its unit (from the glossary, S4-R7). */
export function formatFeature(v: number | null, unit: Unit, windowMonths: number): string {
  if (v === null) return "Missing";
  switch (unit) {
    case "coefficient":
      return v.toFixed(2);
    case "ratio":
      return `${v.toFixed(2)}×`;
    case "months":
      return `${Math.round(v)} of ${windowMonths}`;
    case "months_of_income":
      return `${v.toFixed(2)}× monthly income`;
  }
}

/** A SHAP contribution with its sign: "+1.82" or "−0.36" (a real minus sign). */
export function formatShap(v: number): string {
  const s = Math.abs(v).toFixed(2);
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s;
}
