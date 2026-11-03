import type { Cashflow } from "@/lib/api";
import { formatMoney, formatMonth } from "@/lib/format";
import { cn } from "@/lib/utils";

/** The chart's figures as a table: its text equivalent (S4-R2, S4-R12). */
export function MonthlyTable({ data }: { data: Cashflow }) {
  const win = data.window;
  const inWindow = (start: string) => win !== null && start >= win.start && start < win.end;
  return (
    <div className="overflow-x-auto rounded-lg border border-rule bg-surface">
      <table className="w-full min-w-[36rem] text-sm">
        <caption className="sr-only">Monthly cash flow</caption>
        <thead className="border-b border-rule text-xs text-ink-faint">
          <tr>
            <th scope="col" className="px-4 py-2 text-left font-medium">Month</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Money in</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Money out</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Net</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Closing balance</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Transactions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {data.months.map((m) => (
            <tr key={m.month} className={cn(inWindow(m.start) && "bg-accent/5")}>
              <th scope="row" className="px-4 py-2 text-left font-medium whitespace-nowrap">
                {formatMonth(m.month)}
                {inWindow(m.start) ? <span className="ml-2 text-xs font-normal text-accent-strong">in window</span> : null}
              </th>
              {m.covered ? (
                <>
                  <td className="px-4 py-2 text-right">{formatMoney(m.money_in)}</td>
                  <td className="px-4 py-2 text-right">{formatMoney(m.money_out)}</td>
                  <td className="px-4 py-2 text-right">{formatMoney(m.net)}</td>
                  <td className="px-4 py-2 text-right">{formatMoney(m.closing_balance)}</td>
                </>
              ) : (
                <td colSpan={4} className="px-4 py-2 text-right text-ink-faint">
                  Not fully covered by the stored history, so no figures
                </td>
              )}
              <td className="px-4 py-2 text-right text-ink-soft">{m.transaction_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
