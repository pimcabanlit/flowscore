import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiProblemPanel, load } from "@/components/api-problem";
import { BandBadge } from "@/components/band-badge";
import { CashflowChart } from "@/components/cashflow-chart";
import { MonthlyTable } from "@/components/monthly-table";
import { RunAssessmentButton } from "@/components/run-assessment-button";
import { Badge } from "@/components/ui/badge";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatDayBefore, formatPercentile } from "@/lib/format";


export const metadata = { title: "Cash flow · FlowScore" };

/** S4-R2: one borrower's cash flow, with the window of the latest assessment marked. */
export default async function BorrowerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await load(() => Promise.all([api.borrower(id), api.cashflow(id), api.assessments(id)]));
  if (!res.ok) {
    if (res.error instanceof ApiError && res.error.problem === "not-found") notFound();
    return <ApiProblemPanel error={res.error} />;
  }
  const [borrower, cashflow, history] = res.data;
  const latest = borrower.latest_assessment;

  return (
    <div className="space-y-8">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link href="/" className="text-accent underline decoration-accent/40 hover:decoration-accent">
          Borrowers
        </Link>
        <span aria-hidden className="px-2 text-ink-faint">/</span>
        <span className="text-ink-soft">{borrower.display_name}</span>
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-6">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{borrower.display_name}</h1>
            {borrower.synthetic ? <Badge variant="outline">Synthetic</Badge> : null}
          </div>
          <p className="text-sm text-ink-soft">
            {borrower.id}
            {borrower.history_start && borrower.history_end
              ? ` · history on file ${formatDate(borrower.history_start)} to ${formatDayBefore(borrower.history_end)}`
              : " · no history on file"}
          </p>
        </div>

        <div className="min-w-64 rounded-lg border border-rule bg-surface p-4">
          {latest ? (
            <div className="space-y-2">
              <p className="text-xs text-ink-faint">Latest assessment, as of {formatDate(latest.as_of)}</p>
              <div className="flex flex-wrap items-center gap-3">
                <BandBadge status={latest.status} band={latest.risk_band} />
                {latest.risk_percentile !== null ? (
                  <span className="text-sm text-ink-soft">percentile {formatPercentile(latest.risk_percentile)}</span>
                ) : null}
              </div>
              <Link
                href={`/assessments/${latest.id}`}
                className="inline-block text-sm font-medium text-accent underline decoration-accent/40 hover:decoration-accent"
              >
                Open the assessment and its explanation
              </Link>
            </div>
          ) : borrower.history_end ? (
            <div className="space-y-2">
              <p className="text-sm text-ink-soft">
                Not assessed yet. The assessment uses the 3 months before {formatDate(borrower.history_end)}.
              </p>
              <RunAssessmentButton borrowerId={borrower.id} asOf={borrower.history_end} label="Run assessment" />
            </div>
          ) : (
            <p className="text-sm text-ink-soft">No transactions on file, so there is nothing to assess.</p>
          )}
        </div>
      </header>

      <section aria-labelledby="cashflow" className="space-y-4">
        <h2 id="cashflow" className="text-lg font-semibold">Cash flow by month</h2>
        {cashflow.months.length ? (
          <>
            <div className="rounded-lg border border-rule bg-surface p-4 sm:p-5">
              <CashflowChart data={cashflow} />
            </div>
            <MonthlyTable data={cashflow} />
          </>
        ) : (
          <p className="text-ink-soft">No transactions on file.</p>
        )}
      </section>

      {history.length > 1 ? (
        <section aria-labelledby="history" className="space-y-3">
          <h2 id="history" className="text-lg font-semibold">Earlier assessments</h2>
          <ul className="divide-y divide-rule rounded-lg border border-rule bg-surface text-sm">
            {history.slice(1).map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <Link href={`/assessments/${a.id}`} className="text-accent underline decoration-accent/40 hover:decoration-accent">
                  As of {formatDate(a.as_of)}
                </Link>
                <BandBadge status={a.status} band={a.risk_band} />
                <span className="text-ink-faint">model {a.model_version}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
