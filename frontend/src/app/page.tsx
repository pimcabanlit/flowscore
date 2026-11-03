import Link from "next/link";

import { ApiProblemPanel, load } from "@/components/api-problem";
import { BandBadge } from "@/components/band-badge";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatDate, formatDayBefore, formatPercentile } from "@/lib/format";

export const metadata = { title: "Borrowers · FlowScore" };

/** S4-R1: every borrower with its latest band, percentile and as-of date. */
export default async function BorrowersPage() {
  const res = await load(api.borrowers);
  if (!res.ok) return <ApiProblemPanel error={res.error} />;
  const borrowers = res.data;
  const unassessed = borrowers.filter((b) => b.latest_assessment === null).length;

  return (
    <div className="space-y-6">
      <div className="max-w-3xl space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Borrowers</h1>
        <p className="text-ink-soft">
          Each band places the borrower among the Berka reference borrowers the model learned from: lower, middle or
          higher relative risk. It is a ranking, not a forecast of default.
        </p>
      </div>

      {borrowers.length === 0 ? (
        <section className="rounded-lg border border-rule bg-surface p-6">
          <h2 className="font-semibold">No borrowers yet</h2>
          <p className="mt-1 text-ink-soft">
            Load the synthetic borrowers with <code>python scripts\seed_demo_database.py</code>, then reload.
          </p>
        </section>
      ) : (
        <>
          {unassessed > 0 ? (
            <p className="text-sm text-ink-soft">
              {unassessed} of {borrowers.length} borrowers have no assessment yet. Run{" "}
              <code className="rounded bg-surface px-1">python scripts\assess_demo_borrowers.py</code>, or open a
              borrower and choose Run assessment.
            </p>
          ) : null}
          <div className="overflow-x-auto rounded-lg border border-rule bg-surface">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <caption className="sr-only">Borrowers and their latest assessment</caption>
              <thead className="border-b border-rule text-xs text-ink-faint">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Borrower</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Latest band</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">Percentile</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">As of</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">History on file</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {borrowers.map((b) => {
                  const a = b.latest_assessment;
                  return (
                    <tr key={b.id} className="transition-colors duration-150 hover:bg-paper/70">
                      <td className="px-4 py-2.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            href={`/borrowers/${encodeURIComponent(b.id)}`}
                            className="font-medium text-ink underline decoration-rule-strong hover:decoration-accent"
                          >
                            {b.display_name}
                          </Link>
                          {b.synthetic ? <Badge variant="outline">Synthetic</Badge> : null}
                        </div>
                        <div className="text-xs text-ink-faint">{b.id}</div>
                      </td>
                      <td className="px-4 py-2.5">
                        {a ? <BandBadge status={a.status} band={a.risk_band} /> : <Badge variant="muted">Not assessed</Badge>}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {a?.risk_percentile != null ? formatPercentile(a.risk_percentile) : <span className="text-ink-faint">—</span>}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap">{a ? formatDate(a.as_of) : <span className="text-ink-faint">—</span>}</td>
                      <td className="px-4 py-2.5 whitespace-nowrap text-ink-soft">
                        {b.history_start && b.history_end
                          ? `${formatDate(b.history_start)} to ${formatDayBefore(b.history_end)}`
                          : "None"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
