import type { Cashflow } from "@/lib/api";
import { formatDate, formatDayBefore, formatMoney, formatMoneyShort, formatMonth } from "@/lib/format";

/**
 * Monthly money in and out as bars, the end-of-day balance as a step line, and the latest
 * assessment's window shaded (S4-R2). One y-axis: every series is an amount in the same
 * currency. All figures come from the API; this component only maps them to pixels.
 * A month the history does not fully cover is hatched and labelled, never drawn as zero.
 */

const W = 960;
const H = 320;
const M = { top: 40, right: 16, bottom: 32, left: 64 };
const PW = W - M.left - M.right;
const PH = H - M.top - M.bottom;

const DAY_MS = 86_400_000;
const toTime = (iso: string) => Date.parse(`${iso.slice(0, 10)}T00:00:00Z`);

/** Tick step of 1, 2 or 5 x 10^k giving about five ticks. */
function niceStep(span: number): number {
  const raw = span / 5;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const f = raw / pow;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow;
}

export function CashflowChart({ data }: { data: Cashflow }) {
  const months = data.months;
  if (months.length === 0) return null;

  const values = [
    0,
    ...months.flatMap((m) => [m.money_in, m.money_out, m.closing_balance]),
    ...data.daily_balance.map((d) => d.balance),
  ].filter((v): v is number => v !== null);
  const step = niceStep(Math.max(...values) - Math.min(...values) || 1);
  const yMin = Math.floor(Math.min(...values) / step) * step;
  const yMax = Math.ceil(Math.max(...values) / step) * step;
  const ticks: number[] = [];
  for (let t = yMin; t <= yMax + step / 2; t += step) ticks.push(t);
  const y = (v: number) => M.top + PH - ((v - yMin) / (yMax - yMin)) * PH;

  const band = PW / months.length;
  // x of a calendar date: its month's slot plus the fraction of that month gone by.
  const x = (iso: string) => {
    const t = toTime(iso);
    let i = months.findIndex((m) => t >= toTime(m.start) && t < toTime(m.end));
    if (i < 0) i = t < toTime(months[0].start) ? 0 : months.length - 1;
    const m = months[i];
    const frac = Math.min(1, Math.max(0, (t - toTime(m.start)) / (toTime(m.end) - toTime(m.start))));
    return M.left + (i + frac) * band;
  };
  const xEnd = M.left + PW;

  const barW = Math.min(18, (band - 10) / 2);
  const pts = data.daily_balance;
  let line = "";
  pts.forEach((p, i) => {
    const px = x(p.date) + band / (2 * 31); // the day's end, roughly mid-day
    const py = y(p.balance);
    line += i === 0 ? `M${px.toFixed(1)},${py.toFixed(1)}` : `H${px.toFixed(1)}V${py.toFixed(1)}`;
  });
  if (pts.length) {
    const lastEnd = months[months.length - 1].end;
    const end = Math.min(xEnd, x(new Date(toTime(lastEnd) - DAY_MS).toISOString()) + band / 31);
    line += `H${end.toFixed(1)}`;
  }

  const win = data.window;
  const winX0 = win ? x(win.start) : 0;
  const winX1 = win ? (toTime(win.end) >= toTime(months[months.length - 1].end) ? xEnd : x(win.end)) : 0;

  return (
    <figure className="space-y-3">
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-soft" aria-label="Legend">
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block size-3 rounded-sm bg-in" /> Money in
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block size-3 rounded-sm bg-out" /> Money out
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-0.5 w-4 bg-ink" /> End-of-day balance
        </li>
        {win ? (
          <li className="flex items-center gap-2">
            <span aria-hidden className="inline-block size-3 rounded-sm border border-accent/40 bg-accent/10" /> Window
            used by the latest assessment
          </li>
        ) : null}
      </ul>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-auto w-full min-w-[40rem]"
          role="img"
          aria-label="Monthly money in and money out with the end-of-day balance. The same figures are in the table below."
        >
          <defs>
            <pattern id="uncovered" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="8" stroke="var(--color-rule-strong)" strokeWidth="2" />
            </pattern>
          </defs>

          {win ? (
            <g>
              <rect x={winX0} y={M.top - 30} width={winX1 - winX0} height={PH + 30} fill="var(--color-accent)" opacity={0.08} />
              <line x1={winX0} x2={winX0} y1={M.top - 30} y2={M.top + PH} stroke="var(--color-accent)" strokeOpacity={0.5} />
              <line x1={winX1} x2={winX1} y1={M.top - 30} y2={M.top + PH} stroke="var(--color-accent)" strokeOpacity={0.5} />
              <text x={winX1 - 6} y={M.top - 14} textAnchor="end" fontSize="12" fill="var(--color-accent-strong)" fontWeight={500}>
                Assessment window {formatDate(win.start)} to {formatDayBefore(win.end)}
              </text>
            </g>
          ) : null}

          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={xEnd} y1={y(t)} y2={y(t)} stroke="var(--color-rule)" strokeWidth={t === 0 ? 1.5 : 1} />
              <text x={M.left - 8} y={y(t) + 4} textAnchor="end" fontSize="12" fill="var(--color-ink-faint)">
                {formatMoneyShort(t)}
              </text>
            </g>
          ))}

          {months.map((m, i) => {
            const cx = M.left + i * band + band / 2;
            return (
              <g key={m.month}>
                {m.covered && m.money_in !== null && m.money_out !== null ? (
                  <>
                    <rect x={cx - barW - 1} y={y(Math.max(0, m.money_in))} width={barW} height={Math.abs(y(m.money_in) - y(0))} rx={3} fill="var(--color-in)">
                      <title>{`${formatMonth(m.month)} money in ${formatMoney(m.money_in)}`}</title>
                    </rect>
                    <rect x={cx + 1} y={y(Math.max(0, m.money_out))} width={barW} height={Math.abs(y(m.money_out) - y(0))} rx={3} fill="var(--color-out)">
                      <title>{`${formatMonth(m.month)} money out ${formatMoney(m.money_out)}`}</title>
                    </rect>
                  </>
                ) : (
                  <g>
                    <rect x={M.left + i * band + 2} y={M.top} width={band - 4} height={PH} fill="url(#uncovered)" opacity={0.6}>
                      <title>{`${formatMonth(m.month)}: not fully covered by the stored history, so no figures`}</title>
                    </rect>
                    <text x={cx} y={M.top + PH / 2} textAnchor="middle" fontSize="11" fill="var(--color-ink-soft)">
                      not covered
                    </text>
                  </g>
                )}
                <text x={cx} y={H - 10} textAnchor="middle" fontSize="12" fill="var(--color-ink-soft)">
                  {formatMonth(m.month, true)}
                  {i === 0 || m.month.endsWith("-01") ? ` ${m.month.slice(2, 4)}` : ""}
                </text>
              </g>
            );
          })}

          {line ? <path d={line} fill="none" stroke="var(--color-ink)" strokeWidth={2} strokeLinejoin="round" /> : null}
        </svg>
      </div>
      <figcaption className="text-sm text-ink-faint">
        Money in counts every credit, bank interest included; the model&apos;s income figure leaves interest out.
      </figcaption>
    </figure>
  );
}
