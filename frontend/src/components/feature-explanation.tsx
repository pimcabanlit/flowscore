import { Badge } from "@/components/ui/badge";
import type { Assessment, GlossaryEntry } from "@/lib/api";
import { formatFeature, formatShap } from "@/lib/format";

type Row = {
  feature: string;
  entry: GlossaryEntry;
  value: number | null;
  shap: number | null;
  missing?: { imputed_value: number };
  outOfRange?: { min: number; max: number };
};

function entryFor(feature: string, glossary: GlossaryEntry[]): GlossaryEntry {
  return (
    glossary.find((g) => g.feature === feature) ?? {
      feature,
      label: feature,
      description: "No plain-language description is available for this feature.",
      unit: "coefficient",
      window_months: 3,
    }
  );
}

export function rowsFor(a: Assessment, glossary: GlossaryEntry[]): Row[] {
  return Object.entries(a.features).map(([feature, value]) => {
    const missing = a.missing.find((m) => m.feature === feature);
    const out = a.out_of_range.find((o) => o.feature === feature);
    return {
      feature,
      entry: entryFor(feature, glossary),
      value,
      shap: a.shap?.contributions[feature] ?? null,
      missing: missing ? { imputed_value: missing.imputed_value } : undefined,
      outOfRange: out ? { min: out.min, max: out.max } : undefined,
    };
  });
}

/** Why a feature is flagged, in words (S4-R3). */
export function FlagReason({ row, scored }: { row: Row; scored: boolean }) {
  const { unit, window_months: n } = row.entry;
  if (row.missing)
    return (
      <p className="text-xs text-flag-ink">
        Could not be computed from this window, so the model used the training median,{" "}
        {formatFeature(row.missing.imputed_value, unit, n)}, in its place.
      </p>
    );
  if (row.outOfRange)
    return (
      <p className="text-xs text-flag-ink">
        Outside the range seen in the Berka training data ({formatFeature(row.outOfRange.min, unit, n)} to{" "}
        {formatFeature(row.outOfRange.max, unit, n)}).
        {scored ? " The model has not seen a case like this and treats it as the nearest edge of that range." : null}
      </p>
    );
  return null;
}

function Flags({ row }: { row: Row }) {
  return (
    <>
      {row.missing ? <Badge variant="flag">Missing</Badge> : null}
      {row.outOfRange ? <Badge variant="flag">Outside training range</Badge> : null}
    </>
  );
}

/**
 * One SHAP bar per feature, largest effect first, labelled in plain language with the raw value
 * and the direction in words (S4-R3). Bars grow from a shared zero line: right is towards higher
 * relative risk, left towards lower.
 */
export function ShapBars({ a, glossary }: { a: Assessment; glossary: GlossaryEntry[] }) {
  const rows = rowsFor(a, glossary).sort((p, q) => Math.abs(q.shap ?? 0) - Math.abs(p.shap ?? 0));
  const scale = Math.max(...rows.map((r) => Math.abs(r.shap ?? 0)), 1e-9);
  return (
    <ol className="divide-y divide-rule">
      {rows.map((r) => {
        const s = r.shap ?? 0;
        const pct = (Math.abs(s) / scale) * 50;
        const up = s > 0;
        return (
          <li key={r.feature} className="grid gap-x-6 gap-y-2 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <div className="space-y-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h3 className="font-medium">{r.entry.label}</h3>
                <span className="text-sm font-semibold">{formatFeature(r.value, r.entry.unit, r.entry.window_months)}</span>
                <Flags row={r} />
              </div>
              <p className="max-w-prose text-xs text-ink-faint">{r.entry.description}</p>
              <FlagReason row={r} scored />
            </div>
            <div className="flex flex-col justify-center gap-1">
              <div className="relative h-5" aria-hidden>
                <div className="absolute inset-y-0 left-1/2 w-px bg-rule-strong" />
                <div
                  className={`absolute top-0.5 h-4 ${up ? "rounded-r bg-out" : "rounded-l bg-in"}`}
                  style={up ? { left: "50%", width: `${pct}%` } : { right: "50%", width: `${pct}%` }}
                />
              </div>
              <p className={`text-xs ${up ? "text-right" : "text-left"} text-ink-soft`}>
                <span className="font-semibold text-ink">{formatShap(s)}</span>{" "}
                {s === 0 ? "no effect" : up ? "towards higher relative risk" : "towards lower relative risk"}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Feature values without bars, for a refused assessment (S4-R4). */
export function FeatureValues({ a, glossary }: { a: Assessment; glossary: GlossaryEntry[] }) {
  return (
    <ul className="divide-y divide-rule">
      {rowsFor(a, glossary).map((r) => (
        <li key={r.feature} className="space-y-1 py-3">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h3 className="font-medium">{r.entry.label}</h3>
            <span className="text-sm font-semibold">{formatFeature(r.value, r.entry.unit, r.entry.window_months)}</span>
            <Flags row={r} />
          </div>
          <FlagReason row={r} scored={false} />
        </li>
      ))}
    </ul>
  );
}
