import type { Band, Health } from "@/lib/api";
import { BAND_LABEL, formatPercentile } from "@/lib/format";

/**
 * Where the borrower sits among the Berka reference borrowers, 0 to 100, with the band cut-offs
 * from the model artifact (S4-R3, D22). The signature element of the app: a position on a
 * ruler, not a gauge or a default rate (S4-R8).
 */
export function PercentileStrip({ percentile, band, cutoffs }: { percentile: number; band: Band; cutoffs: Health["band_cutoffs"] }) {
  const zones: { band: Band; from: number; to: number; fill: string; ink: string }[] = [
    { band: "lower", from: 0, to: cutoffs.lower_below, fill: "bg-band-lower", ink: "text-band-lower-ink" },
    { band: "middle", from: cutoffs.lower_below, to: cutoffs.higher_above, fill: "bg-band-middle", ink: "text-band-middle-ink" },
    { band: "higher", from: cutoffs.higher_above, to: 100, fill: "bg-band-higher", ink: "text-band-higher-ink" },
  ];
  return (
    <div className="space-y-2">
      <div className="relative pt-9">
        <div
          className="absolute top-0 -translate-x-1/2 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-xs font-semibold text-white"
          style={{ left: `clamp(2.5rem, ${percentile}%, calc(100% - 2.5rem))` }}
        >
          {formatPercentile(percentile)}
        </div>
        <div className="flex h-8 overflow-hidden rounded-md" role="img" aria-label={`Percentile ${formatPercentile(percentile)} of 100: ${BAND_LABEL[band]}`}>
          {zones.map((z) => (
            <div
              key={z.band}
              className={`${z.fill} ${z.ink} flex items-center justify-center border-r-2 border-surface text-[11px] font-medium last:border-r-0`}
              style={{ width: `${z.to - z.from}%` }}
            >
              <span className="hidden truncate px-1 sm:inline">{BAND_LABEL[z.band].replace(" relative risk", "")}</span>
            </div>
          ))}
        </div>
        <div aria-hidden className="absolute top-7 bottom-0 w-0.5 -translate-x-1/2 bg-ink" style={{ left: `${percentile}%` }} />
      </div>
      <div aria-hidden className="relative h-4 text-[11px] text-ink-faint">
        {[0, cutoffs.lower_below, cutoffs.higher_above, 100].map((t) => (
          <span
            key={t}
            className="absolute -translate-x-1/2 first:translate-x-0 last:-translate-x-full"
            style={{ left: `${t}%` }}
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}
