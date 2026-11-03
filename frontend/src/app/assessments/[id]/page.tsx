import { Ban } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiProblemPanel, load } from "@/components/api-problem";
import { BandBadge } from "@/components/band-badge";
import { FeatureValues, ShapBars } from "@/components/feature-explanation";
import { Notice } from "@/components/notice";
import { PercentileStrip } from "@/components/percentile-strip";
import { Badge } from "@/components/ui/badge";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatDayBefore, formatPercentile } from "@/lib/format";


export const metadata = { title: "Assessment · FlowScore" };

/**
 * S4-R3: the band, the percentile, one SHAP bar per feature, the flags and the D21 notice.
 * S4-R4: a refused assessment explains the refusal instead. No default-rate figure anywhere (S4-R8).
 */
export default async function AssessmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const res = await load(async () => {
    const a = await api.assessment(id);
    const [borrower, glossary, health] = await Promise.all([api.borrower(a.borrower_id), api.glossary(), api.health()]);
    return { a, borrower, glossary, health };
  });
  if (!res.ok) {
    if (res.error instanceof ApiError && res.error.problem === "not-found") notFound();
    return <ApiProblemPanel error={res.error} />;
  }
  const { a, borrower, glossary, health } = res.data;
  const scored = a.status === "scored" && a.risk_band !== null && a.risk_percentile !== null;
  const flagged = a.missing.length + a.out_of_range.length;

  return (
    <div className="space-y-8">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link href="/" className="text-accent underline decoration-accent/40 hover:decoration-accent">
          Borrowers
        </Link>
        <span aria-hidden className="px-2 text-ink-faint">/</span>
        <Link
          href={`/borrowers/${encodeURIComponent(borrower.id)}`}
          className="text-accent underline decoration-accent/40 hover:decoration-accent"
        >
          {borrower.display_name}
        </Link>
        <span aria-hidden className="px-2 text-ink-faint">/</span>
        <span className="text-ink-soft">Assessment</span>
      </nav>

      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Assessment of {borrower.display_name}</h1>
          {borrower.synthetic ? <Badge variant="outline">Synthetic</Badge> : null}
        </div>
        <dl className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
          <div className="flex gap-2">
            <dt className="text-ink-faint">As of</dt>
            <dd>{formatDate(a.as_of)}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-ink-faint">Window</dt>
            <dd>
              {formatDate(a.window_start)} to {formatDayBefore(a.as_of)}
            </dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-ink-faint">Model</dt>
            <dd>{a.model_version}</dd>
          </div>
        </dl>
      </header>

      <Notice notice={a.notice} />

      {scored ? (
        <section aria-labelledby="band" className="space-y-5 rounded-lg border border-rule bg-surface p-5 sm:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <h2 id="band" className="text-lg font-semibold">
              Relative risk band
            </h2>
            <BandBadge status={a.status} band={a.risk_band} />
          </div>
          <PercentileStrip percentile={a.risk_percentile!} band={a.risk_band!} cutoffs={health.band_cutoffs} />
          <p className="max-w-prose text-ink-soft">
            Percentile <strong className="font-semibold text-ink">{formatPercentile(a.risk_percentile!)}</strong>: the model
            ranks this borrower riskier than {formatPercentile(a.risk_percentile!)}% of the Berka reference borrowers. The
            bands split that ranking at {health.band_cutoffs.lower_below} and {health.band_cutoffs.higher_above}.
          </p>
        </section>
      ) : (
        <section aria-labelledby="refused" className="space-y-3 rounded-lg border border-flag-rule bg-surface p-5 sm:p-6">
          <h2 id="refused" className="flex items-center gap-2 text-lg font-semibold">
            <Ban aria-hidden className="size-5 text-flag-ink" />
            No band: this assessment was refused
          </h2>
          <p className="max-w-prose text-ink-soft">
            More than half of the features that could be computed are outside the range of the Berka training data. The
            model would be guessing beyond anything it has seen, so FlowScore gives no band rather than a misleading one.
          </p>
          {a.out_of_range.length ? (
            <p className="text-sm font-medium">
              Outside the training range: {a.out_of_range.length} of {Object.keys(a.features).length - a.missing.length}{" "}
              computed features.
            </p>
          ) : null}
        </section>
      )}

      <section aria-labelledby="drivers" className="space-y-3">
        <div className="space-y-1">
          <h2 id="drivers" className="text-lg font-semibold">
            {scored ? "What moved the ranking" : "Feature values"}
          </h2>
          <p className="max-w-prose text-sm text-ink-soft">
            {scored
              ? "Each bar is the feature's SHAP contribution, in log-odds: how far this borrower's value moved the model's score away from that of an average reference borrower, and in which direction."
              : "The values computed from the window, with the reason each one is flagged."}
            {flagged ? ` ${flagged} feature${flagged > 1 ? "s are" : " is"} flagged below.` : " No feature is missing or outside the training range."}
          </p>
        </div>
        <div className="rounded-lg border border-rule bg-surface px-5 sm:px-6">
          {scored && a.shap ? <ShapBars a={a} glossary={glossary} /> : <FeatureValues a={a} glossary={glossary} />}
        </div>
      </section>

      <p className="text-xs text-ink-faint">
        Assessment {a.id} · snapshot {a.snapshot_id} · stored {formatDate(a.created_at)} · feature code{" "}
        {a.features_version.slice(0, 12)}
      </p>
    </div>
  );
}
